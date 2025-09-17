import json
import os
from typing import Any, Dict
from twilio.rest import Client

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

        if not self.account_sid or not self.auth_token:
            raise ValueError("Twilio credentials not configured")

        self.client = Client(self.account_sid, self.auth_token)

    def send_template_message(
        self, to: str, content_sid: str, content_variables: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Send WhatsApp template message via Twilio.
        Use if we have pre-approved templates
        Use for initiated messages only
        """
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
