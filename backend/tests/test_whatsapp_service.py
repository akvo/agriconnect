import os
from unittest.mock import Mock, patch

import pytest

from services.whatsapp_service import WhatsAppService, load_message_templates


class TestWhatsAppService:
    def test_init_with_credentials(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TWILIO_WHATSAPP_NUMBER": "whatsapp:+1234567890",
                "TESTING": "false",  # Test production path with mocked client
            },
        ):
            with patch("services.whatsapp_service.Client") as mock_client:
                service = WhatsAppService()

                assert service.account_sid == "test_sid"
                assert service.auth_token == "test_token"
                assert service.whatsapp_number == "whatsapp:+1234567890"
                mock_client.assert_called_once_with("test_sid", "test_token")

    def test_init_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                ValueError, match="Twilio credentials not configured"
            ):
                WhatsAppService()

    def test_init_missing_account_sid(self):
        with patch.dict(
            os.environ, {"TWILIO_AUTH_TOKEN": "test_token"}, clear=True
        ):
            with pytest.raises(
                ValueError, match="Twilio credentials not configured"
            ):
                WhatsAppService()

    def test_init_missing_auth_token(self):
        with patch.dict(
            os.environ, {"TWILIO_ACCOUNT_SID": "test_sid"}, clear=True
        ):
            with pytest.raises(
                ValueError, match="Twilio credentials not configured"
            ):
                WhatsAppService()

    def test_init_default_whatsapp_number(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "false",  # Test production path
            },
        ):
            with patch("services.whatsapp_service.Client"):
                service = WhatsAppService()
                assert service.whatsapp_number == "whatsapp:+14155238886"

    def test_send_message_success(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "false",  # Test production path with mocked client
            },
        ):
            with patch("services.whatsapp_service.Client") as mock_client:
                mock_message = Mock()
                mock_message.sid = "SM123"
                mock_message.status = "sent"
                mock_message.to = "whatsapp:+255123456789"
                mock_message.body = "Test message"

                mock_client_instance = Mock()
                mock_client_instance.messages.create.return_value = (
                    mock_message
                )
                mock_client.return_value = mock_client_instance

                service = WhatsAppService()
                result = service.send_message("+255123456789", "Test message")

                assert result == {
                    "sid": "SM123",
                    "status": "sent",
                    "to": "whatsapp:+255123456789",
                    "body": "Test message",
                }

                mock_client_instance.messages.create.assert_called_once_with(
                    from_="whatsapp:+14155238886",
                    body="Test message",
                    to="whatsapp:+255123456789",
                )

    def test_send_message_twilio_error(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "false",  # Test production path with mocked client
            },
        ):
            with patch("services.whatsapp_service.Client") as mock_client:
                mock_client_instance = Mock()
                mock_client_instance.messages.create.side_effect = Exception(
                    "Twilio API error"
                )
                mock_client.return_value = mock_client_instance

                service = WhatsAppService()

                with pytest.raises(
                    Exception,
                    match="Failed to send WhatsApp message: Twilio API error",
                ):
                    service.send_message("+255123456789", "Test message")

    def test_send_welcome_message_english(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "true",  # Use testing mode for these tests
            },
        ):
            with patch("services.whatsapp_service.Client"):
                service = WhatsAppService()

                with patch.object(service, "send_message") as mock_send:
                    mock_send.return_value = {"sid": "SM123", "status": "sent"}

                    result = service.send_welcome_message(
                        "+255123456789", "en"
                    )

                    templates = load_message_templates()
                    expected_message = templates["welcome_messages"]["en"]
                    mock_send.assert_called_once_with(
                        "+255123456789", expected_message
                    )
                    assert result == {"sid": "SM123", "status": "sent"}

    def test_send_welcome_message_swahili(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "true",  # Use testing mode
            },
        ):
            with patch("services.whatsapp_service.Client"):
                service = WhatsAppService()

                with patch.object(service, "send_message") as mock_send:
                    mock_send.return_value = {"sid": "SM456", "status": "sent"}

                    result = service.send_welcome_message(
                        "+255123456789", "sw"
                    )

                    templates = load_message_templates()
                    expected_message = templates["welcome_messages"]["sw"]
                    mock_send.assert_called_once_with(
                        "+255123456789", expected_message
                    )
                    assert result == {"sid": "SM456", "status": "sent"}

    def test_send_welcome_message_unknown_language(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "true",  # Use testing mode
            },
        ):
            with patch("services.whatsapp_service.Client"):
                service = WhatsAppService()

                with patch.object(service, "send_message") as mock_send:
                    mock_send.return_value = {"sid": "SM789", "status": "sent"}

                    service.send_welcome_message("+255123456789", "fr")

                    # Should default to English
                    templates = load_message_templates()
                    expected_message = templates["welcome_messages"]["en"]
                    mock_send.assert_called_once_with(
                        "+255123456789", expected_message
                    )

    def test_send_welcome_message_no_language(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "true",  # Use testing mode
            },
        ):
            with patch("services.whatsapp_service.Client"):
                service = WhatsAppService()

                with patch.object(service, "send_message") as mock_send:
                    mock_send.return_value = {"sid": "SM999", "status": "sent"}

                    service.send_welcome_message("+255123456789")

                    # Should default to English
                    templates = load_message_templates()
                    expected_message = templates["welcome_messages"]["en"]
                    mock_send.assert_called_once_with(
                        "+255123456789", expected_message
                    )

    def test_send_message_custom_whatsapp_number(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TWILIO_WHATSAPP_NUMBER": "+1987654321",
                "TESTING": "false",  # Test production path
            },
        ):
            with patch("services.whatsapp_service.Client") as mock_client:
                mock_message = Mock()
                mock_message.sid = "SM123"
                mock_message.status = "sent"
                mock_message.to = "whatsapp:+255123456789"
                mock_message.body = "Test message"

                mock_client_instance = Mock()
                mock_client_instance.messages.create.return_value = (
                    mock_message
                )
                mock_client.return_value = mock_client_instance

                service = WhatsAppService()
                service.send_message("+255123456789", "Test message")

                mock_client_instance.messages.create.assert_called_once_with(
                    from_="whatsapp:+1987654321",  # Custom number used
                    body="Test message",
                    to="whatsapp:+255123456789",
                )

    def test_send_template_message_success(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "false",  # Test production path
            },
        ):
            with patch("services.whatsapp_service.Client") as mock_client:
                mock_message = Mock()
                mock_message.sid = "SM123"
                mock_message.status = "sent"
                mock_message.to = "whatsapp:+255123456789"
                mock_message.body = "Hello John, welcome to AgriConnect!"

                mock_client_instance = Mock()
                mock_client_instance.messages.create.return_value = (
                    mock_message
                )
                mock_client.return_value = mock_client_instance

                service = WhatsAppService()
                result = service.send_template_message(
                    "+255123456789", "HXabc123def456", {"1": "John"}
                )

                assert result == {
                    "sid": "SM123",
                    "status": "sent",
                    "to": "whatsapp:+255123456789",
                    "body": "Hello John, welcome to AgriConnect!",
                }

                mock_client_instance.messages.create.assert_called_once_with(
                    from_="whatsapp:+14155238886",
                    to="whatsapp:+255123456789",
                    content_sid="HXabc123def456",
                    content_variables={"1": "John"},
                )

    def test_send_template_message_twilio_error(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "false",  # Test production path
            },
        ):
            with patch("services.whatsapp_service.Client") as mock_client:
                mock_client_instance = Mock()
                mock_client_instance.messages.create.side_effect = Exception(
                    "Invalid content SID"
                )
                mock_client.return_value = mock_client_instance

                service = WhatsAppService()
                failed_message = "Failed to send WhatsApp template message"
                invalid_content = "Invalid content SID"

                with pytest.raises(
                    Exception,
                    match="{}: {}".format(failed_message, invalid_content),
                ):
                    service.send_template_message(
                        "+255123456789", "invalid_sid", {"1": "John"}
                    )

    def test_send_template_message_custom_whatsapp_number(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TWILIO_WHATSAPP_NUMBER": "whatsapp:+1987654321",
                "TESTING": "false",  # Test production path
            },
        ):
            with patch("services.whatsapp_service.Client") as mock_client:
                mock_message = Mock()
                mock_message.sid = "SM456"
                mock_message.status = "sent"
                mock_message.to = "whatsapp:+255123456789"
                mock_message.body = "Broadcast message"

                mock_client_instance = Mock()
                mock_client_instance.messages.create.return_value = (
                    mock_message
                )
                mock_client.return_value = mock_client_instance

                service = WhatsAppService()
                service.send_template_message(
                    "+255123456789",
                    "HXbroadcast789",
                    {"1": "AgriConnect Updates"},
                )

                mock_client_instance.messages.create.assert_called_once_with(
                    from_="whatsapp:+1987654321",  # Custom number used
                    to="whatsapp:+255123456789",
                    content_sid="HXbroadcast789",
                    content_variables={"1": "AgriConnect Updates"},
                )

    def test_send_template_message_multiple_variables(self):
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "false",  # Test production path
            },
        ):
            with patch("services.whatsapp_service.Client") as mock_client:
                mock_message = Mock()
                mock_message.sid = "SM789"
                mock_message.status = "sent"
                mock_message.to = "whatsapp:+255123456789"
                mock_message.body = "Hello John, you have 5 unread messages"

                mock_client_instance = Mock()
                mock_client_instance.messages.create.return_value = (
                    mock_message
                )
                mock_client.return_value = mock_client_instance

                service = WhatsAppService()
                result = service.send_template_message(
                    "+255123456789", "HXreconnect123", {"1": "John", "2": "5"}
                )

                assert result == {
                    "sid": "SM789",
                    "status": "sent",
                    "to": "whatsapp:+255123456789",
                    "body": "Hello John, you have 5 unread messages",
                }

                mock_client_instance.messages.create.assert_called_once_with(
                    from_="whatsapp:+14155238886",
                    to="whatsapp:+255123456789",
                    content_sid="HXreconnect123",
                    content_variables={"1": "John", "2": "5"},
                )

    def test_send_confirmation_template_success(self):
        """Test sending confirmation template with AI answer"""
        # Set TESTING=false
        # to test the real code path (with mocked Twilio client)
        env_vars = {
            "TWILIO_ACCOUNT_SID": "test_sid",
            "TWILIO_AUTH_TOKEN": "test_token",
            "WHATSAPP_CONFIRMATION_TEMPLATE_SID": "HX123abc456",
            "TESTING": "false",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with patch("services.whatsapp_service.Client") as mock_client:
                with patch(
                    "services.whatsapp_service.settings"
                ) as mock_settings:
                    mock_settings.whatsapp_confirmation_template_sid = (
                        "HX123abc456"
                    )

                    mock_message = Mock()
                    mock_message.sid = "SM999"
                    mock_message.status = "sent"

                    mock_client_instance = Mock()
                    mock_client_instance.messages.create.return_value = (
                        mock_message
                    )
                    mock_client.return_value = mock_client_instance

                    service = WhatsAppService()
                    result = service.send_confirmation_template(
                        "+255123456789",
                        "Your crops need watering this week.",
                    )

                    assert result == {"sid": "SM999", "status": "sent"}

                    # Verify content_variables is JSON string
                    call_args = mock_client_instance.messages.create.call_args
                    import json

                    content_vars = json.loads(
                        call_args.kwargs["content_variables"]
                    )
                    assert (
                        content_vars["ai_answer"]
                        == "Your crops need watering this week."
                    )

    def test_send_confirmation_template_no_template_sid(self):
        """Test fallback to plain message when no template SID configured"""
        # Set TESTING=false to test real code path (with mocked Twilio client)
        env_vars = {
            "TWILIO_ACCOUNT_SID": "test_sid",
            "TWILIO_AUTH_TOKEN": "test_token",
            "TESTING": "false",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with patch("services.whatsapp_service.Client") as mock_client:
                with patch(
                    "services.whatsapp_service.settings"
                ) as mock_settings:
                    mock_settings.whatsapp_confirmation_template_sid = None

                    mock_message = Mock()
                    mock_message.sid = "SM888"
                    mock_message.status = "sent"
                    mock_message.to = "whatsapp:+255123456789"
                    mock_message.body = "AI answer text"

                    mock_client_instance = Mock()
                    mock_client_instance.messages.create.return_value = (
                        mock_message
                    )
                    mock_client.return_value = mock_client_instance

                    service = WhatsAppService()
                    result = service.send_confirmation_template(
                        "+255123456789", "AI answer text"
                    )

                    # Should fallback to send_message
                    assert result["sid"] == "SM888"
                    mock_client_instance.messages.create.assert_called_once()

    def test_send_confirmation_template_testing_mode(self):
        """Test confirmation template returns mock response in TESTING mode"""
        with patch.dict(
            os.environ,
            {
                "TWILIO_ACCOUNT_SID": "test_sid",
                "TWILIO_AUTH_TOKEN": "test_token",
                "TESTING": "1",
            },
        ):
            with patch("services.whatsapp_service.Client"):
                service = WhatsAppService()
                result = service.send_confirmation_template(
                    "+255123456789", "Test AI answer"
                )

                assert result == {"sid": "TESTING_MODE", "status": "sent"}

    def test_send_confirmation_template_twilio_error(self):
        """Test confirmation template fallback on Twilio error"""
        # Set TESTING=false to test real code path (with mocked Twilio client)
        env_vars = {
            "TWILIO_ACCOUNT_SID": "test_sid",
            "TWILIO_AUTH_TOKEN": "test_token",
            "TESTING": "false",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with patch("services.whatsapp_service.Client") as mock_client:
                with patch(
                    "services.whatsapp_service.settings"
                ) as mock_settings:
                    mock_settings.whatsapp_confirmation_template_sid = (
                        "HX123abc456"
                    )

                    mock_client_instance = Mock()
                    # Template fails, then fallback succeeds
                    mock_message = Mock()
                    mock_message.sid = "SM777"
                    mock_message.status = "sent"
                    mock_message.to = "whatsapp:+255123456789"
                    mock_message.body = "Fallback message"

                    mock_client_instance.messages.create.side_effect = [
                        Exception("Template error"),
                        mock_message,
                    ]
                    mock_client.return_value = mock_client_instance

                    service = WhatsAppService()
                    result = service.send_confirmation_template(
                        "+255123456789", "AI answer"
                    )

                    # Should fallback to send_message
                    assert result["sid"] == "SM777"
                    assert mock_client_instance.messages.create.call_count == 2

    def test_load_message_templates_success(self):
        """Test loading WhatsApp message templates from JSON file"""
        mock_templates = {
            "welcome_messages": {"en": "Welcome!", "sw": "Karibu!"}
        }

        with patch("builtins.open", create=True):
            with patch("json.load", return_value=mock_templates):
                result = load_message_templates()
                assert result == mock_templates

    def test_load_message_templates_file_not_found(self):
        """Test handling when template file is not found"""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = load_message_templates()
            assert result == {}

    def test_load_message_templates_json_decode_error(self):
        """Test handling when JSON is invalid"""
        import json

        with patch("builtins.open", create=True):
            with patch(
                "json.load", side_effect=json.JSONDecodeError("", "", 0)
            ):
                result = load_message_templates()
                assert result == {}
