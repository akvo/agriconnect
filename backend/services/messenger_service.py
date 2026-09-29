"""
Facebook Messenger Service.

Provides outbound messaging, quick replies, typing indicators,
webhook HMAC-SHA256 signature verification, and Meta platform
signed_request data deletion decoding for Facebook Messenger.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import requests

from config import settings

logger = logging.getLogger(__name__)


class MessengerService:
    """Service for interacting with Meta Graph API for Facebook Messenger."""

    def __init__(
        self,
        page_access_token: Optional[str] = None,
        app_secret: Optional[str] = None,
        api_version: Optional[str] = None,
        is_testing: Optional[bool] = None,
    ):
        if is_testing is not None:
            self.is_testing = is_testing
        else:
            self.is_testing = os.getenv("TEST", "").lower() in (
                "true",
                "1",
            ) or os.getenv("TESTING", "").lower() in ("true", "1")

        self.page_access_token = (
            page_access_token
            if page_access_token is not None
            else settings.messenger_page_access_token
        )
        self.app_secret = (
            app_secret
            if app_secret is not None
            else settings.messenger_app_secret
        )
        self.api_version = (
            api_version
            if api_version is not None
            else settings.messenger_graph_api_version
        )
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def verify_signature(
        self, payload_bytes: bytes, signature_header: Optional[str]
    ) -> bool:
        """
        Verify incoming webhook X-Hub-Signature-256 header.

        Uses timing-attack safe comparison via hmac.compare_digest.
        """
        if self.is_testing and not self.app_secret:
            return True

        if not signature_header or not signature_header.startswith("sha256="):
            logger.warning(
                f"Missing or malformed signature header: {signature_header}"
            )
            return False

        if not self.app_secret:
            logger.warning(
                "MESSENGER_APP_SECRET is not configured for signature check"
            )
            return False

        expected_sig = hmac.new(
            self.app_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        provided_sig = signature_header.split("sha256=")[1]
        matches = hmac.compare_digest(expected_sig, provided_sig)
        if not matches:
            logger.warning(
                "HMAC-SHA256 signature mismatch. Please verify that "
                "MESSENGER_APP_SECRET in .env exactly matches the App Secret "
                "in your Meta App settings (Basic Settings -> App Secret)."
            )
        return matches

    def parse_signed_request(
        self, signed_request: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse and verify Meta signed_request for platform data deletion.

        Format: <encoded_sig>.<encoded_payload>
        """
        if not signed_request or "." not in signed_request:
            return None

        try:
            encoded_sig, encoded_payload = signed_request.split(".", 1)

            # Fix base64url padding
            padded_payload = encoded_payload + "=" * (
                -len(encoded_payload) % 4
            )
            padded_sig = encoded_sig + "=" * (-len(encoded_sig) % 4)

            sig = base64.urlsafe_b64decode(padded_sig.encode("utf-8"))
            payload_bytes = base64.urlsafe_b64decode(
                padded_payload.encode("utf-8")
            )
            data = json.loads(payload_bytes.decode("utf-8"))

            if self.is_testing and not self.app_secret:
                return data

            if not self.app_secret:
                logger.warning(
                    "MESSENGER_APP_SECRET is not configured for signed request"
                )
                return None

            expected_sig = hmac.new(
                self.app_secret.encode("utf-8"),
                encoded_payload.encode("utf-8"),
                hashlib.sha256,
            ).digest()

            if not hmac.compare_digest(sig, expected_sig):
                logger.warning(
                    "Invalid signature in Meta signed_request payload"
                )
                return None

            return data
        except Exception as e:
            logger.error(f"Error parsing signed_request: {e}")
            return None

    def send_message(self, recipient_psid: str, text: str) -> Dict[str, Any]:
        """Send a standard text message to a Facebook Messenger user."""
        if self.is_testing:
            mock_mid = f"mid.test.{uuid.uuid4().hex[:12]}"
            logger.info(
                f"[TEST MODE] Messenger sent to {recipient_psid}: {text[:50]}"
            )
            return {"recipient_id": recipient_psid, "message_id": mock_mid}

        url = (
            f"{self.base_url}/me/messages"
            f"?access_token={self.page_access_token}"
        )
        payload = {
            "recipient": {"id": recipient_psid},
            "message": {"text": text},
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def send_quick_replies(
        self,
        recipient_psid: str,
        text: str,
        options: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Send a message with Quick Reply buttons."""
        if self.is_testing:
            mock_mid = f"mid.test.{uuid.uuid4().hex[:12]}"
            logger.info(
                f"[TEST MODE] Messenger quick replies sent to {recipient_psid}"
            )
            return {"recipient_id": recipient_psid, "message_id": mock_mid}

        quick_replies = [
            {
                "content_type": "text",
                "title": opt.get("title", "")[:20],
                "payload": opt.get("payload", "")[:1000],
            }
            for opt in options
        ]

        url = (
            f"{self.base_url}/me/messages"
            f"?access_token={self.page_access_token}"
        )
        payload = {
            "recipient": {"id": recipient_psid},
            "message": {
                "text": text,
                "quick_replies": quick_replies,
            },
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def send_typing_indicator(
        self, recipient_psid: str, is_typing: bool = True
    ) -> Dict[str, Any]:
        """Send typing indicator (typing_on / typing_off)."""
        action = "typing_on" if is_typing else "typing_off"

        if self.is_testing:
            return {"recipient_id": recipient_psid}

        url = (
            f"{self.base_url}/me/messages"
            f"?access_token={self.page_access_token}"
        )
        payload = {
            "recipient": {"id": recipient_psid},
            "sender_action": action,
        }

        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        return response.json()
