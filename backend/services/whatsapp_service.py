import json
import logging
import os
import re
import uuid
import phonenumbers
import httpx
from typing import Any, Dict, Optional
from models.message import Message, DeliveryStatus
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from sqlalchemy.sql import func
from phonenumbers import NumberParseException
from sqlalchemy.orm import Session
from unittest.mock import Mock

from config import settings

logger = logging.getLogger(__name__)

# Store content sid that we get from Twilio console
# How to get content sid:
# https://www.twilio.com/docs/whatsapp/api/message-templates
# Example template
# greetings, broadcast, reconnection
# GREETINGS
# "HI {{1}}, welcome to AgriConnect! How can we assist you today?"
# BROADCAST
# "Hello {{1}}, check out our latest agricultural tips and updates!"
# RECONNECTION
# "There are unread messages from AgriConnect: {{1}}"


def load_message_templates():
    """Load WhatsApp messages from template."""
    try:
        with open(
            "templates/whatsapp_messages.json", "r", encoding="utf-8"
        ) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading WhatsApp messages: {e}")
        return {}


# Load WhatsApp messages from template
WHATSAPP_MESSAGES = load_message_templates()
MAX_WHATSAPP_MESSAGE_LENGTH = 1500


class WhatsAppService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        whatsapp_number = os.getenv(
            "TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886"
        )

        # Ensure whatsapp: prefix is present
        if not whatsapp_number.startswith("whatsapp:"):
            whatsapp_number = f"whatsapp:{whatsapp_number}"

        self.whatsapp_number = whatsapp_number

        # CRITICAL: Prevent real API calls during testing
        # Check if we're in test mode to avoid sending real messages
        self.testing_mode = os.getenv("TESTING", "").lower() in (
            "true",
            "1",
            "yes",
        )

        if self.testing_mode:
            # Create a mock client for testing - NO REAL API CALLS
            logger.info(
                "WhatsAppService initialized in TESTING mode - "
                "using mock client"
            )

            self.client = Mock()

            # CRITICAL: Use side_effect to generate UNIQUE SIDs for each call
            # This prevents database unique constraint violations when
            # multiple messages are created in tests
            def mock_create_message(**kwargs):
                mock_message = Mock()
                # Generate unique SID
                # using UUID to avoid DB constraint violations
                mock_message.sid = f"MOCK_SID_{uuid.uuid4().hex[:12].upper()}"
                mock_message.status = "sent"
                mock_message.to = kwargs.get("to", "whatsapp:+255000000000")
                mock_message.body = kwargs.get("body", "Mock message body")
                return mock_message

            self.client.messages.create.side_effect = mock_create_message
        else:
            # Production mode - use real Twilio client
            if not self.account_sid or not self.auth_token:
                raise ValueError("Twilio credentials not configured")

            logger.info(
                "WhatsAppService initialized in PRODUCTION mode - "
                "using real Twilio client"
            )
            self.client = Client(self.account_sid, self.auth_token)

    @staticmethod
    def sanitize_whatsapp_content(text: str) -> str:
        """
        Sanitize text to prevent Twilio error 63013 (Channel policy violation).

        Prevents:
        - More than 4 consecutive whitespaces
        - Consecutive newlines (multiple blank lines)
        - Wrapping quotation marks
        - Trailing punctuation followed by multiple spaces
        - Empty or null strings

        Args:
            text: The text to sanitize

        Returns:
            Sanitized text safe for WhatsApp template variables
        """
        if not text or not text.strip():
            return "Response is being processed."

        # Remove leading/trailing whitespace first
        text = text.strip()

        # Remove wrapping quotation marks (single or double quotes)
        # that wrap the entire response
        if (text.startswith('"') and text.endswith('"')) or (
            text.startswith("'") and text.endswith("'")
        ):
            text = text[1:-1].strip()

        # Replace more than 4 consecutive spaces with 3 spaces
        text = re.sub(r" {4,}", "   ", text)

        # Replace consecutive newlines (2+ newlines) with single newline
        text = re.sub(r"\n{2,}", "\n", text)

        # Replace tabs with single space
        text = text.replace("\t", " ")

        # Fix consecutive punctuation (e.g., "results.." becomes "results.")
        text = re.sub(r"([.!?]){2,}", r"\1", text)

        # Fix punctuation followed by multiple spaces
        # (e.g., "results. " becomes "results. ")
        text = re.sub(r"([.!?,;:])\s{2,}", r"\1 ", text)

        # Remove any remaining leading/trailing whitespace
        text = text.strip()

        # Ensure we still have content after sanitization
        if not text:
            return "Response is being processed."

        return text

    def get_template_sid(
        self, template_type: str, customer_language: Optional[str] = None
    ) -> str:
        """
        Get the appropriate template SID based on customer language.

        Args:
            template_type: Type of template
                ("confirmation", "reconnection", "broadcast")
            customer_language: Customer's language preference ("en" or "sw")

        Returns:
            Template SID string
        """
        from config import settings

        # Map template types to config attributes
        template_map = {
            "confirmation": {
                "en": settings.whatsapp_confirmation_template_sid,
                "sw": settings.whatsapp_confirmation_template_sid_sw,
            },
            "reconnection": {
                "en": settings.whatsapp_reconnection_template_sid,
                "sw": settings.whatsapp_reconnection_template_sid_sw,
            },
            "broadcast": {
                "en": settings.whatsapp_broadcast_template_sid,
                "sw": settings.whatsapp_broadcast_template_sid_sw,
            },
        }

        if template_type not in template_map:
            logger.warning(
                f"[WhatsAppService] Unknown template type: {template_type}, "
                f"defaulting to confirmation"
            )
            template_type = "confirmation"

        # Get SID for customer's language, fallback to English
        language = (
            customer_language if customer_language in ["en", "sw"] else "en"
        )
        sid = template_map[template_type].get(language)

        # Fallback to English if Swahili SID not available
        if not sid and language == "sw":
            logger.warning(
                f"[WhatsAppService] Swahili template not configured for "
                f"{template_type}, using English"
            )
            sid = template_map[template_type].get("en")

        logger.info(
            f"[WhatsAppService] Selected {template_type} template "
            f"for language '{language}': {sid}"
        )

        return sid

    def send_template_message(
        self, to: str, content_sid: str, content_variables: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Send WhatsApp template message via Twilio.
        Use if we have pre-approved templates
        Use for initiated messages only

        Note: Use get_template_sid() to get the appropriate SID
        based on language
        """
        if self.testing_mode:
            logger.info(
                f"[TESTING MODE] Mocking template message to {to} "
                f"with template {content_sid}"
            )

        try:
            message = self.client.messages.create(
                from_=self.whatsapp_number,
                to=f"whatsapp:{to}",
                content_sid=content_sid,
                content_variables=json.dumps(content_variables),
            )
            return {
                "sid": message.sid,
                "status": message.status,
                "to": message.to,
                "body": message.body,
            }
        except Exception as e:
            raise Exception(f"Failed to send WhatsApp template message: {e}")

    def send_message(
        self, to_number: str, message_body: str
    ) -> Dict[str, Any]:
        """Send WhatsApp message via Twilio."""
        if self.testing_mode:
            logger.info(
                f"[TESTING MODE] Mocking WhatsApp message to {to_number}: "
                f"{message_body[:50]}..."
            )

        try:
            message = self.client.messages.create(
                from_=self.whatsapp_number,
                body=message_body,
                to=f"whatsapp:{to_number}",
            )
            return {
                "sid": message.sid,
                "status": message.status,
                "to": message.to,
                "body": message.body,
            }
        except Exception as e:
            raise Exception(f"Failed to send WhatsApp message: {e}")

    def send_welcome_message(
        self, to_number: str, language: str = "en"
    ) -> Dict[str, Any]:
        """Send welcome message to new customer."""
        welcome_messages = WHATSAPP_MESSAGES.get("welcome_messages", {})

        message = welcome_messages.get(
            language, welcome_messages.get("en", "")
        )
        if not message:
            print("No welcome message found for language: {}".format(language))
            return {}

        return self.send_message(to_number, message)

    def send_confirmation_template(
        self, to_number: str, ai_answer: str
    ) -> Dict[str, Any]:
        """
        Send AI answer as a separate message, then send confirmation template
        asking if farmer needs human help.

        Template buttons:
        - "Yes" (ButtonPayload="escalate") - Farmer wants to talk to human
        - "No" (ButtonPayload="none") - Farmer is satisfied

        Args:
            to_number: Farmer's phone number
            ai_answer: The AI-generated answer to send as separate message

        Returns:
            Response from Twilio with template message SID
        """
        # Sanitize AI answer to prevent Twilio error 63013
        sanitized_answer = self.sanitize_whatsapp_content(ai_answer)

        if self.testing_mode:
            # Skip sending messages in testing mode - NO REAL API CALLS
            logger.info(
                f"[TESTING MODE] Mocking AI answer and confirmation template "
                f"to {to_number}"
            )
            return {"sid": "TESTING_MODE", "status": "sent"}

        # Step 1: Send AI answer as a regular message
        try:
            answer_response = self.send_message(to_number, sanitized_answer)
            logger.info(
                f"✓ Sent AI answer to {to_number}: {answer_response['sid']}"
            )
        except Exception as e:
            logger.error(f"✗ Error sending AI answer: {e}")
            # If we can't send the answer, still try to send the template
            pass

        # Step 2: Send confirmation template
        template_sid = settings.whatsapp_confirmation_template_sid

        if not template_sid:
            # If no template configured, we already sent the answer
            logger.warning(
                "No confirmation template SID configured - "
                "only AI answer was sent"
            )
            return answer_response

        try:
            # Send template message without variables
            message = self.client.messages.create(
                from_=self.whatsapp_number,
                to=f"whatsapp:{to_number}",
                content_sid=template_sid,
            )

            logger.info(
                f"✓ Sent confirmation template to {to_number}: {message.sid}"
            )
            return {"sid": message.sid, "status": message.status}

        except Exception as e:
            logger.error(f"✗ Error sending confirmation template: {e}")
            # If template fails but answer was sent, return answer response
            return answer_response

    def download_twilio_media(
        self, media_url: str, save_path: str
    ) -> Optional[str]:
        """
        Download media file from Twilio.

        Twilio media URLs are PUBLIC by default (no auth required).
        However, if HTTP auth is enabled in Twilio Console, we'll try
        with Basic Auth as fallback.

        Args:
            media_url: Twilio media URL
                (e.g., https://api.twilio.com/.../Media/...)
            save_path: Local path to save file
                (e.g., /tmp/audio_12345.ogg)

        Returns:
            Path to downloaded file, or None if download failed
        """
        if self.testing_mode:
            logger.info(
                f"[TESTING MODE] Mocking media download from {media_url}"
            )
            # Create empty file for testing
            with open(save_path, "wb") as f:
                f.write(b"fake audio data for testing")
            return save_path

        try:
            # Try without auth first (media URLs are public by default)
            try:
                response = httpx.get(
                    media_url, timeout=30.0, follow_redirects=True
                )
                response.raise_for_status()

                logger.info(
                    f"✓ Downloaded media from Twilio (no auth): "
                    f"{len(response.content)} bytes → {save_path}"
                )

            except httpx.HTTPStatusError as e:
                # If 401/403, try with Basic Auth (in case auth is enabled)
                if e.response.status_code in [401, 403]:
                    logger.info(
                        "Media URL requires auth, retrying with credentials"
                    )
                    auth = (self.account_sid, self.auth_token)
                    response = httpx.get(
                        media_url,
                        auth=auth,
                        timeout=30.0,
                        follow_redirects=True,
                    )
                    response.raise_for_status()

                    logger.info(
                        f"✓ Downloaded media from Twilio (with auth): "
                        f"{len(response.content)} bytes → {save_path}"
                    )
                else:
                    raise  # Re-raise other HTTP errors

            # Save to file
            with open(save_path, "wb") as f:
                f.write(response.content)

            return save_path

        except httpx.HTTPError as e:
            logger.error(f"✗ Failed to download Twilio media: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Unexpected error downloading media: {e}")
            return None

    @staticmethod
    def validate_and_format_phone_number(phone: str) -> str:
        """
        Validate and format phone number to E.164 format.

        Args:
            phone: Phone number in any format

        Returns:
            E.164 formatted number (e.g., +255712345678)

        Raises:
            ValueError: If phone number is invalid
        """
        try:
            # Remove whatsapp: prefix if present
            phone = phone.replace("whatsapp:", "").strip()

            # If number doesn't start with +, try adding it
            if not phone.startswith("+"):
                phone = "+" + phone

            # Parse phone number (None = detect country from number)
            parsed = phonenumbers.parse(phone, None)

            # Validate
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError(f"Invalid phone number: {phone}")

            # Format to E.164
            formatted = phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )

            logger.info(f"Validated phone: {phone} → {formatted}")
            return formatted

        except NumberParseException as e:
            raise ValueError(f"Cannot parse phone number '{phone}': {e}")

    def send_message_with_tracking(
        self,
        to_number: str,
        message_body: str,
        message_id: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Send WhatsApp message with delivery tracking and error handling.

        Args:
            to_number: Recipient phone number
            message_body: Message content
            message_id: Database message ID (for status updates)
            db: Database session (for status updates)

        Returns:
            Dict with sid, status, error info

        Raises:
            ValueError: Invalid phone number
            TwilioRestException: Twilio API error
        """
        # Validate phone number first
        try:
            validated_number = self.validate_and_format_phone_number(to_number)
        except ValueError as e:
            logger.error(f"Phone validation failed: {e}")
            if message_id and db:
                self._update_message_status(
                    db,
                    message_id,
                    delivery_status="FAILED",
                    error_code="INVALID",  # Shortened to fit 10-char limit
                    error_message=str(e),
                )
            raise

        # Testing mode bypass
        if self.testing_mode:
            logger.info(
                f"[TESTING MODE] Mocking message to {validated_number}"
            )
            mock_sid = f"MOCK_SID_{uuid.uuid4().hex[:12].upper()}"

            # Update database status even in testing mode
            if message_id and db:
                self._update_message_status(
                    db,
                    message_id,
                    delivery_status="SENT",
                    message_sid=mock_sid,
                )

            return {
                "sid": mock_sid,
                "status": "sent",
                "to": f"whatsapp:{validated_number}",
                "body": message_body,
                "error_code": None,
            }

        try:
            # Send via Twilio
            message = self.client.messages.create(
                from_=self.whatsapp_number,
                body=message_body,
                to=f"whatsapp:{validated_number}",
            )

            # Check for errors
            if message.error_code:
                logger.error(
                    f"Twilio error {message.error_code}: "
                    f"{message.error_message}"
                )
                if message_id and db:
                    self._update_message_status(
                        db,
                        message_id,
                        delivery_status="FAILED",
                        error_code=str(message.error_code),
                        error_message=message.error_message,
                    )
                raise TwilioRestException(
                    status=400,
                    uri=f"/Messages/{message.sid}",
                    msg=message.error_message,
                    code=message.error_code,
                )

            # Update status to QUEUED/SENT
            if message_id and db:
                # Map Twilio status to our enum
                delivery_status = self._map_twilio_status(message.status)
                self._update_message_status(
                    db,
                    message_id,
                    delivery_status=delivery_status,
                    message_sid=message.sid,
                )

            logger.info(
                f"✓ Message sent: {message.sid} (status: {message.status})"
            )

            return {
                "sid": message.sid,
                "status": message.status,
                "to": message.to,
                "body": message.body,
                "error_code": None,
            }

        except TwilioRestException as e:
            logger.error(f"Twilio API error {e.code}: {e.msg}")

            # Update message status
            if message_id and db:
                # Determine if error is retryable
                # Rate limit, server errors
                retryable_codes = [20429, 20500, 20503]
                status = "PENDING" if e.code in retryable_codes else "FAILED"

                self._update_message_status(
                    db,
                    message_id,
                    delivery_status=status,
                    error_code=str(e.code),
                    error_message=e.msg,
                )

            raise

    def _map_twilio_status(self, twilio_status: str) -> str:
        """Map Twilio status to our DeliveryStatus enum value"""
        status_map = {
            "queued": "QUEUED",
            "sending": "SENDING",
            "sent": "SENT",
            "delivered": "DELIVERED",
            "read": "READ",
            "failed": "FAILED",
            "undelivered": "UNDELIVERED",
        }
        return status_map.get(twilio_status.lower(), "PENDING")

    def _update_message_status(
        self,
        db: Session,
        message_id: int,
        delivery_status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        message_sid: Optional[str] = None,
    ):
        """Update message delivery status in database"""
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            logger.warning(f"Message {message_id} not found for status update")
            return

        # Convert string to enum if it's a string
        if isinstance(delivery_status, str):
            try:
                delivery_status = DeliveryStatus[delivery_status]
            except KeyError:
                logger.error(f"Invalid delivery status: {delivery_status}")
                return

        message.delivery_status = delivery_status

        if error_code:
            message.twilio_error_code = error_code
        if error_message:
            message.twilio_error_message = error_message
        if message_sid:
            message.message_sid = message_sid

        if delivery_status == DeliveryStatus.DELIVERED:
            message.delivered_at = func.now()

        db.commit()
        logger.info(
            f"Updated message {message_id} status to {delivery_status.value}"
        )
