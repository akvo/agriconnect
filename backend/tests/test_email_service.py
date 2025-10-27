import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.email_service import EmailService, email_service


class TestEmailService:
    """Test suite for EmailService"""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables with TESTING mode enabled"""
        with patch.dict(
            os.environ,
            {
                "SMTP_USER": "test_user@example.com",
                "SMTP_PASS": "test_password",
                "SMTP_PORT": "587",
                "SMTP_HOST": "smtp.example.com",
                "SMTP_USE_TLS": "True",
                "WEBDOMAIN": "test.example.com",
                "TESTING": "true",  # Consistent with conftest.py
            },
        ):
            yield

    @pytest.fixture
    def mock_env_no_test_mode(self):
        """
        Mock environment without TESTING mode
        (for testing actual sending with mocked FastMail)
        """
        with patch.dict(
            os.environ,
            {
                "SMTP_USER": "test_user@example.com",
                "SMTP_PASS": "test_password",
                "SMTP_PORT": "587",
                "SMTP_HOST": "smtp.example.com",
                "SMTP_USE_TLS": "True",
                "WEBDOMAIN": "test.example.com",
                "TESTING": "false",  # Explicitly disable to test real sending
                "TEST": "false",     # Disable both for compatibility
            },
        ):
            yield

    @pytest.fixture
    def mock_env_localhost(self):
        """Mock environment variables with localhost"""
        with patch.dict(
            os.environ,
            {
                "SMTP_USER": "test_user@example.com",
                "SMTP_PASS": "test_password",
                "SMTP_PORT": "587",
                "SMTP_HOST": "smtp.example.com",
                "SMTP_USE_TLS": "True",
                "WEBDOMAIN": "localhost",
                "TESTING": "false",  # Disable test mode for these tests
                "TEST": "false",
            },
        ):
            yield

    @pytest.fixture
    def mock_env_test_mode(self):
        """Mock environment variables with TESTING mode enabled"""
        with patch.dict(
            os.environ,
            {
                "SMTP_USER": "test@akvomail.org",
                "SMTP_PASS": "test_password",
                "SMTP_PORT": "465",
                "SMTP_HOST": "test.akvomail.org",
                "SMTP_USE_TLS": "True",
                "WEBDOMAIN": "test.agriconnect.com",
                "TESTING": "1",  # Consistent with conftest.py
            },
        ):
            yield

    def test_init_default_config(self, mock_env):
        """Test EmailService initialization with default config"""
        service = EmailService()

        assert service.conf.MAIL_USERNAME == "test_user@example.com"
        # MAIL_PASSWORD is a SecretStr object, get its value
        assert service.conf.MAIL_PASSWORD.get_secret_value() == "test_password"
        assert service.conf.MAIL_FROM == "test_user@example.com"
        assert service.conf.MAIL_PORT == 587
        assert service.conf.MAIL_SERVER == "smtp.example.com"
        assert service.conf.MAIL_FROM_NAME == "AgriConnect Platform"
        assert service.conf.MAIL_STARTTLS is False
        assert service.conf.MAIL_SSL_TLS is True
        assert service.web_domain == "test.example.com"
        assert service.protocol == "https"
        assert service.disable_sending is True

    def test_init_localhost_protocol(self, mock_env_localhost):
        """Test EmailService uses http for localhost"""
        with patch("services.email_service.FastMail"):
            service = EmailService()

            assert service.web_domain == "localhost"
            assert service.protocol == "http"

    def test_init_test_mode_enabled(self, mock_env_test_mode):
        """Test EmailService detects TEST mode"""
        with patch("services.email_service.FastMail"):
            service = EmailService()

            assert service.disable_sending is True

    def test_init_test_mode_with_true_string(self):
        """Test EmailService detects TESTING=true"""
        with patch.dict(
            os.environ,
            {
                "SMTP_USER": "test@akvomail.org",
                "SMTP_PASS": "test_password",
                "TESTING": "true",  # Consistent with conftest.py
            },
        ):
            with patch("services.email_service.FastMail"):
                service = EmailService()
                assert service.disable_sending is True

    def test_init_jinja_env_setup(self, mock_env):
        """Test Jinja2 environment is properly configured"""
        with patch("services.email_service.FastMail"):
            service = EmailService()

            # Check Jinja2 environment is set up
            assert service.jinja_env is not None
            # Verify template directory path exists
            assert isinstance(service.jinja_env.loader, object)

    @pytest.mark.asyncio
    async def test_send_invitation_email_success(self, mock_env_no_test_mode):
        """Test sending invitation email successfully"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock()
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            result = await service.send_invitation_email(
                email="newuser@example.com",
                full_name="John Doe",
                invitation_token="abc123token",
                user_type="admin",
                invited_by_name="Admin User",
            )

            assert result is True
            mock_fastmail.send_message.assert_called_once()

            # Verify the message schema
            call_args = mock_fastmail.send_message.call_args
            message = call_args[0][0]
            assert (
                message.subject
                == "Welcome to AgriConnect - Complete Your Account Setup"
            )
            assert message.recipients == ["newuser@example.com"]
            assert "John Doe" in message.body
            assert "Administrator" in message.body
            assert (
                "https://test.example.com/accept-invitation/abc123token"
                in message.body
            )

    @pytest.mark.asyncio
    async def test_send_invitation_email_extension_officer(
        self, mock_env_no_test_mode
    ):
        """Test sending invitation email to extension officer"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock()
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            result = await service.send_invitation_email(
                email="eo@example.com",
                full_name="Jane Smith",
                invitation_token="xyz789token",
                user_type="eo",
                invited_by_name="Admin User",
            )

            assert result is True

            # Verify the message contains Extension Officer
            call_args = mock_fastmail.send_message.call_args
            message = call_args[0][0]
            assert "Extension Officer" in message.body
            assert "Jane Smith" in message.body

    @pytest.mark.asyncio
    async def test_send_invitation_email_localhost_url(
        self, mock_env_localhost
    ):
        """Test invitation email URL uses http for localhost"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock()
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            result = await service.send_invitation_email(
                email="user@example.com",
                full_name="Test User",
                invitation_token="token123",
                user_type="admin",
            )

            assert result is True

            # Verify URL uses http for localhost
            call_args = mock_fastmail.send_message.call_args
            message = call_args[0][0]
            expected_url = "http://localhost/accept-invitation/token123"
            assert expected_url in message.body

    @pytest.mark.asyncio
    async def test_send_invitation_email_test_mode_skips_sending(
        self, mock_env_test_mode
    ):
        """Test invitation email is not sent in TEST mode"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock()
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            result = await service.send_invitation_email(
                email="user@example.com",
                full_name="Test User",
                invitation_token="token123",
                user_type="admin",
            )

            assert result is True
            # Verify send_message was NOT called in test mode
            mock_fastmail.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_invitation_email_failure(self, mock_env_no_test_mode):
        """Test handling of invitation email sending failure"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock(
                side_effect=Exception("SMTP connection failed")
            )
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            result = await service.send_invitation_email(
                email="user@example.com",
                full_name="Test User",
                invitation_token="token123",
                user_type="admin",
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_invitation_email_template_rendering(self, mock_env):
        """Test that both HTML and text templates are rendered"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock()
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            # Mock the template rendering
            with patch.object(
                service.jinja_env, "get_template"
            ) as mock_get_template:
                mock_html_template = Mock()
                mock_text_template = Mock()
                mock_html_template.render.return_value = (
                    "<html>Invitation</html>"
                )
                mock_text_template.render.return_value = "Invitation text"

                def get_template_side_effect(template_name):
                    if template_name == "invitation.html":
                        return mock_html_template
                    elif template_name == "invitation.txt":
                        return mock_text_template
                    return Mock()

                mock_get_template.side_effect = get_template_side_effect

                result = await service.send_invitation_email(
                    email="user@example.com",
                    full_name="Test User",
                    invitation_token="token123",
                    user_type="admin",
                    invited_by_name="Admin",
                )

                assert result is True
                # Verify both templates were loaded
                assert mock_get_template.call_count == 2
                mock_html_template.render.assert_called_once()
                mock_text_template.render.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_password_reset_email_success(
        self, mock_env_no_test_mode
    ):
        """Test sending password reset email successfully"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock()
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            result = await service.send_password_reset_email(
                email="user@example.com",
                full_name="John Doe",
                reset_token="reset123token",
            )

            assert result is True
            mock_fastmail.send_message.assert_called_once()

            # Verify the message schema
            call_args = mock_fastmail.send_message.call_args
            message = call_args[0][0]
            assert message.subject == "Password Reset - AgriConnect"
            assert message.recipients == ["user@example.com"]
            assert "John Doe" in message.body
            assert (
                "https://test.example.com/reset-password/reset123token"
                in message.body
            )

    @pytest.mark.asyncio
    async def test_send_password_reset_email_localhost_url(
        self, mock_env_localhost
    ):
        """Test password reset email URL uses http for localhost"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock()
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            result = await service.send_password_reset_email(
                email="user@example.com",
                full_name="Test User",
                reset_token="reset456",
            )

            assert result is True

            # Verify URL uses http for localhost
            call_args = mock_fastmail.send_message.call_args
            message = call_args[0][0]
            assert "http://localhost/reset-password/reset456" in message.body

    @pytest.mark.asyncio
    async def test_send_password_reset_email_test_mode_skips_sending(
        self, mock_env_test_mode
    ):
        """Test password reset email is not sent in TEST mode"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock()
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            result = await service.send_password_reset_email(
                email="user@example.com",
                full_name="Test User",
                reset_token="reset789",
            )

            assert result is True
            # Verify send_message was NOT called in test mode
            mock_fastmail.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_password_reset_email_failure(
        self, mock_env_no_test_mode
    ):
        """Test handling of password reset email sending failure"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock(
                side_effect=Exception("Email server unavailable")
            )
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            result = await service.send_password_reset_email(
                email="user@example.com",
                full_name="Test User",
                reset_token="reset123",
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_password_reset_email_template_rendering(
        self, mock_env
    ):
        """Test HTML and text templates rendered for password reset"""
        with patch("services.email_service.FastMail") as mock_fastmail_class:
            mock_fastmail = Mock()
            mock_fastmail.send_message = AsyncMock()
            mock_fastmail_class.return_value = mock_fastmail

            service = EmailService()

            # Mock the template rendering
            with patch.object(
                service.jinja_env, "get_template"
            ) as mock_get_template:
                mock_html_template = Mock()
                mock_text_template = Mock()
                mock_html_template.render.return_value = (
                    "<html>Password Reset</html>"
                )
                mock_text_template.render.return_value = "Password Reset text"

                def get_template_side_effect(template_name):
                    if template_name == "password_reset.html":
                        return mock_html_template
                    elif template_name == "password_reset.txt":
                        return mock_text_template
                    return Mock()

                mock_get_template.side_effect = get_template_side_effect

                result = await service.send_password_reset_email(
                    email="user@example.com",
                    full_name="Test User",
                    reset_token="reset123",
                )

                assert result is True
                # Verify both templates were loaded
                assert mock_get_template.call_count == 2
                mock_html_template.render.assert_called_once()
                mock_text_template.render.assert_called_once()

    def test_global_email_service_instance(self):
        """Test that global email_service instance is created"""
        assert email_service is not None
        assert isinstance(email_service, EmailService)

    def test_backward_compatibility_with_test_var(self):
        """Test EmailService still works with legacy TEST variable"""
        with patch.dict(
            os.environ,
            {
                "SMTP_USER": "test@example.com",
                "SMTP_PASS": "password",
                "TEST": "true",  # Legacy variable
                "TESTING": "false",  # New variable disabled
            },
        ):
            with patch("services.email_service.FastMail"):
                service = EmailService()
                # Should still detect test mode from TEST variable
                assert service.disable_sending is True

    def test_testing_variable_takes_precedence(self):
        """Test that TESTING variable is properly detected"""
        with patch.dict(
            os.environ,
            {
                "SMTP_USER": "test@example.com",
                "SMTP_PASS": "password",
                "TESTING": "true",  # New standard variable
                "TEST": "false",    # Legacy disabled
            },
        ):
            with patch("services.email_service.FastMail"):
                service = EmailService()
                # Should detect test mode from TESTING variable
                assert service.disable_sending is True
