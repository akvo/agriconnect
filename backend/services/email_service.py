import logging
import os
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from jinja2 import Environment, FileSystemLoader
from pydantic import EmailStr

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending invitations and notifications"""

    def __init__(self):
        self.conf = ConnectionConfig(
            MAIL_USERNAME=os.getenv("SMTP_USER", "agriconnect@akvomail.org"),
            MAIL_PASSWORD=os.getenv("SMTP_PASS", ""),
            MAIL_FROM=os.getenv("SMTP_USER", "agriconnect@akvomail.org"),
            MAIL_PORT=int(os.getenv("SMTP_PORT", "465")),
            MAIL_SERVER=os.getenv("SMTP_HOST", "akvomail.org"),
            MAIL_FROM_NAME="AgriConnect Platform",
            MAIL_STARTTLS=False,
            MAIL_SSL_TLS=os.getenv("SMTP_USE_TLS", "True").lower() == "true",
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
        )
        self.fastmail = FastMail(self.conf)
        self.web_domain = os.getenv("WEBDOMAIN", "localhost")
        self.protocol = "https" if self.web_domain != "localhost" else "http"

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))

    async def send_invitation_email(
        self,
        email: EmailStr,
        full_name: str,
        invitation_token: str,
        user_type: str,
        invited_by_name: str = "Administrator",
    ) -> bool:
        """
        Send invitation email to new user

        Args:
            email: User's email address
            full_name: User's full name
            invitation_token: Unique invitation token
            user_type: User type (admin/eo)
            invited_by_name: Name of the admin who sent invitation

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            invitation_url = "{}://{}/accept-invitation/{}".format(
                self.protocol, self.web_domain, invitation_token
            )

            user_type_display = (
                "Administrator"
                if user_type == "admin"
                else "Extension Officer"
            )

            # Render HTML template
            html_template = self.jinja_env.get_template("invitation.html")
            html_content = html_template.render(
                full_name=full_name,
                email=email,
                user_type_display=user_type_display,
                invited_by_name=invited_by_name,
                invitation_url=invitation_url,
                user_type=user_type,
            )

            # Render text template
            text_template = self.jinja_env.get_template("invitation.txt")
            text_content = text_template.render(
                full_name=full_name,
                email=email,
                user_type_display=user_type_display,
                invited_by_name=invited_by_name,
                invitation_url=invitation_url,
            )

            message = MessageSchema(
                subject="Welcome to AgriConnect - Complete Your Account Setup",
                recipients=[email],
                body=html_content,
                alternative_body=text_content,
                subtype=MessageType.html,
            )

            await self.fastmail.send_message(message)
            logger.info(f"Invitation email sent successfully to {email}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to send invitation email to {email}: {str(e)}"
            )
            return False

    async def send_password_reset_email(
        self, email: EmailStr, full_name: str, reset_token: str
    ) -> bool:
        """
        Send password reset email (if needed in future)

        Args:
            email: User's email address
            full_name: User's full name
            reset_token: Password reset token

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            reset_url = "{}://{}/reset-password/{}".format(
                self.protocol, self.web_domain, reset_token
            )

            # Render HTML template
            html_template = self.jinja_env.get_template("password_reset.html")
            html_content = html_template.render(
                full_name=full_name, reset_url=reset_url
            )

            # Render text template
            text_template = self.jinja_env.get_template("password_reset.txt")
            text_content = text_template.render(
                full_name=full_name, reset_url=reset_url
            )

            message = MessageSchema(
                subject="Password Reset - AgriConnect",
                recipients=[email],
                body=html_content,
                alternative_body=text_content,
                subtype=MessageType.html,
            )

            await self.fastmail.send_message(message)
            logger.info(f"Password reset email sent successfully to {email}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to send password reset email to {email}: {str(e)}"
            )
            return False


# Global email service instance
email_service = EmailService()
