import json
import logging
import os
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
        Send AI answer with confirmation template
        asking if farmer needs human help.

        Template buttons:
        - "Yes" (ButtonPayload="escalate") - Farmer wants to talk to human
        - "No" (ButtonPayload="none") - Farmer is satisfied

        Args:
            to_number: Farmer's phone number
            ai_answer: The AI-generated answer to include in template

        Returns:
            Response from Twilio with message SID
        """
        if self.testing_mode:
            # Skip sending templates in testing mode - NO REAL API CALLS
            logger.info(
                f"[TESTING MODE] Mocking confirmation template to {to_number}"
            )
            return {"sid": "TESTING_MODE", "status": "sent"}
        template_sid = settings.whatsapp_confirmation_template_sid

        if not template_sid:
            # Fallback: send plain message without template
            logger.warning(
                "No confirmation template SID configured -"
                " sending plain message"
            )
            return self.send_message(to_number, ai_answer)

        try:
            # Send template message with AI answer as variable
            message = self.client.messages.create(
                from_=self.whatsapp_number,
                to=f"whatsapp:{to_number}",
                content_sid=template_sid,
                content_variables=json.dumps(
                    {"ai_answer": ai_answer}  # Template variable for AI answer
                ),
            )

            logger.info(
                f"✓ Sent confirmation template to {to_number}: {message.sid}"
            )
            return {"sid": message.sid, "status": message.status}

        except Exception as e:
            logger.error(f"✗ Error sending confirmation template: {e}")
            # Fallback: send plain message
            return self.send_message(to_number, ai_answer)
