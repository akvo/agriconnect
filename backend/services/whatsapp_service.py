import os
from twilio.rest import Client
from typing import Dict, Any


class WhatsAppService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "+14155238886")
        
        if not self.account_sid or not self.auth_token:
            raise ValueError("Twilio credentials not configured")
        
        self.client = Client(self.account_sid, self.auth_token)

    def send_message(self, to_number: str, message_body: str) -> Dict[str, Any]:
        """Send WhatsApp message via Twilio."""
        try:
            message = self.client.messages.create(
                from_=self.whatsapp_number,
                body=message_body,
                to=f"whatsapp:{to_number}"
            )
            return {
                "sid": message.sid,
                "status": message.status,
                "to": message.to,
                "body": message.body
            }
        except Exception as e:
            raise Exception(f"Failed to send WhatsApp message: {e}")

    def send_welcome_message(self, to_number: str, language: str = "en") -> Dict[str, Any]:
        """Send welcome message to new customer."""
        welcome_messages = {
            "en": "Welcome to AgriConnect! We're here to help you with agricultural information and support. How can we assist you today?",
            "sw": "Karibu AgriConnect! Tuko hapa kukusaidia na maelezo na msaada wa kilimo. Tunawezaje kukusaidia leo?"
        }
        
        message = welcome_messages.get(language, welcome_messages["en"])
        return self.send_message(to_number, message)