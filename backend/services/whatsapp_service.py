import json
import logging
import os
import re
from typing import Any, Dict
from twilio.rest import Client

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
            "yes"
        )

        if self.testing_mode:
            # Create a mock client for testing - NO REAL API CALLS
            logger.info(
                "WhatsAppService initialized in TESTING mode - "
                "using mock client"
            )
            from unittest.mock import Mock
            import uuid

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
        if (text.startswith('"') and text.endswith('"')) or \
           (text.startswith("'") and text.endswith("'")):
            text = text[1:-1].strip()

        # Replace more than 4 consecutive spaces with 3 spaces
        text = re.sub(r' {4,}', '   ', text)

        # Replace consecutive newlines (2+ newlines) with single newline
        text = re.sub(r'\n{2,}', '\n', text)

        # Replace tabs with single space
        text = text.replace('\t', ' ')

        # Fix consecutive punctuation (e.g., "results.." becomes "results.")
        text = re.sub(r'([.!?]){2,}', r'\1', text)

        # Fix punctuation followed by multiple spaces
        # (e.g., "results. " becomes "results. ")
        text = re.sub(r'([.!?,;:])\s{2,}', r'\1 ', text)

        # Remove any remaining leading/trailing whitespace
        text = text.strip()

        # Ensure we still have content after sanitization
        if not text:
            return "Response is being processed."

        # Ensure text length does not exceed WhatsApp limits
        max_length = 1500
        if len(text) > max_length:
            text = text[:max_length - 3].rstrip() + "..."
        return text

    def send_template_message(
        self, to: str, content_sid: str, content_variables: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Send WhatsApp template message via Twilio.
        Use if we have pre-approved templates
        Use for initiated messages only
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
                content_variables=content_variables,
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
