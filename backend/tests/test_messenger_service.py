import base64
import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from services.messenger_service import MessengerService


def generate_signed_request(payload_dict: dict, secret: str) -> str:
    """Helper to generate a valid Meta signed_request string."""
    payload_json = json.dumps(payload_dict, separators=(",", ":"))
    encoded_payload = (
        base64.urlsafe_b64encode(payload_json.encode("utf-8"))
        .decode("utf-8")
        .rstrip("=")
    )

    sig = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    encoded_sig = base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")

    return f"{encoded_sig}.{encoded_payload}"


class TestMessengerService:
    """
    Test suite for MessengerService Graph API client
    and cryptographic helpers.
    """

    def test_init_default_and_env(self):
        service = MessengerService(
            page_access_token="test_page_token",
            app_secret="test_secret",
            api_version="v21.0",
            is_testing=True,
        )
        assert service.page_access_token == "test_page_token"
        assert service.app_secret == "test_secret"
        assert service.api_version == "v21.0"
        assert service.is_testing is True

    def test_verify_signature_valid(self):
        secret = "my_app_secret_123"
        payload = b'{"object":"page","entry":[]}'
        expected_hash = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        valid_header = f"sha256={expected_hash}"

        service = MessengerService(app_secret=secret, is_testing=False)
        assert service.verify_signature(payload, valid_header) is True

    def test_verify_signature_invalid(self):
        secret = "my_app_secret_123"
        payload = b'{"object":"page","entry":[]}'
        invalid_header = "sha256=invalidhash1234567890"

        service = MessengerService(app_secret=secret, is_testing=False)
        assert service.verify_signature(payload, invalid_header) is False

    def test_verify_signature_malformed_header(self):
        secret = "my_app_secret_123"
        payload = b'{"object":"page","entry":[]}'

        service = MessengerService(app_secret=secret, is_testing=False)
        assert service.verify_signature(payload, "") is False
        assert service.verify_signature(payload, "invalid_no_prefix") is False
        assert service.verify_signature(payload, None) is False

    def test_verify_signature_in_testing_mode(self):
        # In testing mode without secret, verify_signature returns True
        service = MessengerService(app_secret="", is_testing=True)
        assert service.verify_signature(b"{}", "sha256=any") is True

    def test_parse_signed_request_valid(self):
        secret = "test_app_secret"
        payload = {
            "algorithm": "HMAC-SHA256",
            "issued_at": 1700000000,
            "user_id": "psid_987654321",
        }
        signed_request = generate_signed_request(payload, secret)

        service = MessengerService(app_secret=secret, is_testing=False)
        parsed = service.parse_signed_request(signed_request)
        assert parsed is not None
        assert parsed.get("user_id") == "psid_987654321"

    def test_parse_signed_request_tampered(self):
        secret = "test_app_secret"
        payload = {
            "algorithm": "HMAC-SHA256",
            "user_id": "psid_987654321",
        }
        signed_request = generate_signed_request(payload, secret)
        tampered_request = signed_request[:-3] + "xyz"

        service = MessengerService(app_secret=secret, is_testing=False)
        parsed = service.parse_signed_request(tampered_request)
        assert parsed is None

    def test_parse_signed_request_invalid_format(self):
        service = MessengerService(app_secret="test_secret", is_testing=False)
        assert service.parse_signed_request("invalid_no_dot") is None
        assert service.parse_signed_request("") is None
        assert service.parse_signed_request(None) is None

    def test_send_message_testing_mode(self):
        service = MessengerService(is_testing=True)
        response = service.send_message(
            recipient_psid="123456789", text="Hello Farmer!"
        )
        assert response["recipient_id"] == "123456789"
        assert "message_id" in response
        assert response["message_id"].startswith("mid.test.")

    @patch("services.messenger_service.requests.post")
    def test_send_message_production(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "recipient_id": "123456789",
            "message_id": "mid.real.12345",
        }
        mock_post.return_value = mock_response

        service = MessengerService(
            page_access_token="real_token",
            api_version="v21.0",
            is_testing=False,
        )
        response = service.send_message("123456789", "Habari!")

        assert response["message_id"] == "mid.real.12345"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        expected_url = (
            "https://graph.facebook.com/v21.0/me/messages"
            "?access_token=real_token"
        )
        assert args[0] == expected_url
        assert kwargs["json"]["recipient"]["id"] == "123456789"
        assert kwargs["json"]["message"]["text"] == "Habari!"

    def test_send_quick_replies_testing_mode(self):
        service = MessengerService(is_testing=True)
        options = [
            {"title": "Option A", "payload": "PAYLOAD_A"},
            {"title": "Option B", "payload": "PAYLOAD_B"},
        ]
        response = service.send_quick_replies(
            recipient_psid="123456789",
            text="Please choose:",
            options=options,
        )
        assert response["recipient_id"] == "123456789"
        assert "message_id" in response

    @patch("services.messenger_service.requests.post")
    def test_send_quick_replies_production(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "recipient_id": "123456789",
            "message_id": "mid.real.qr.12345",
        }
        mock_post.return_value = mock_response

        service = MessengerService(
            page_access_token="real_token", is_testing=False
        )
        options = [
            {"title": "Mahindi", "payload": "CROP_MAIZE"},
            {"title": "Kahawa", "payload": "CROP_COFFEE"},
        ]
        response = service.send_quick_replies(
            "123456789", "Chagua zao:", options
        )

        assert response["message_id"] == "mid.real.qr.12345"
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        quick_replies = kwargs["json"]["message"]["quick_replies"]
        assert len(quick_replies) == 2
        assert quick_replies[0]["title"] == "Mahindi"
        assert quick_replies[0]["payload"] == "CROP_MAIZE"

    @patch("services.messenger_service.requests.post")
    def test_send_typing_indicator(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"recipient_id": "123456789"}
        mock_post.return_value = mock_response

        service = MessengerService(
            page_access_token="real_token", is_testing=False
        )
        service.send_typing_indicator("123456789", is_typing=True)

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["sender_action"] == "typing_on"
