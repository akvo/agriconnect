import os
from typing import List
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
import logging

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
            VALIDATE_CERTS=True
        )
        self.fastmail = FastMail(self.conf)
        self.web_domain = os.getenv("WEBDOMAIN", "localhost")
        self.protocol = "https" if self.web_domain != "localhost" else "http"
    
    async def send_invitation_email(
        self,
        email: EmailStr,
        full_name: str,
        invitation_token: str,
        user_type: str,
        invited_by_name: str = "Administrator"
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
            invitation_url = f"{self.protocol}://{self.web_domain}/accept-invitation/{invitation_token}"
            
            user_type_display = "Administrator" if user_type == "admin" else "Extension Officer"
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Welcome to AgriConnect</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
                        color: white;
                        padding: 30px 20px;
                        text-align: center;
                        border-radius: 8px 8px 0 0;
                    }}
                    .content {{
                        background: #ffffff;
                        padding: 30px 20px;
                        border: 1px solid #e5e7eb;
                        border-top: none;
                    }}
                    .footer {{
                        background: #f9fafb;
                        padding: 20px;
                        text-align: center;
                        border: 1px solid #e5e7eb;
                        border-top: none;
                        border-radius: 0 0 8px 8px;
                        color: #6b7280;
                        font-size: 14px;
                    }}
                    .cta-button {{
                        display: inline-block;
                        background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
                        color: white;
                        padding: 12px 30px;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: 600;
                        margin: 20px 0;
                    }}
                    .info-box {{
                        background: #f0f9ff;
                        border: 1px solid #0ea5e9;
                        border-radius: 6px;
                        padding: 15px;
                        margin: 20px 0;
                    }}
                    .warning-box {{
                        background: #fef3cd;
                        border: 1px solid #f59e0b;
                        border-radius: 6px;
                        padding: 15px;
                        margin: 20px 0;
                        font-size: 14px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🌱 Welcome to AgriConnect</h1>
                    <p>Agricultural Extension Platform</p>
                </div>
                
                <div class="content">
                    <h2>Hello {full_name}!</h2>
                    
                    <p>You have been invited to join <strong>AgriConnect</strong> as a <strong>{user_type_display}</strong> by {invited_by_name}.</p>
                    
                    <div class="info-box">
                        <strong>📧 Your Account Details:</strong><br>
                        <strong>Email:</strong> {email}<br>
                        <strong>Role:</strong> {user_type_display}
                    </div>
                    
                    <p>To complete your account setup and start using the platform, please click the button below to set your password:</p>
                    
                    <div style="text-align: center;">
                        <a href="{invitation_url}" class="cta-button">Accept Invitation & Set Password</a>
                    </div>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background: #f3f4f6; padding: 10px; border-radius: 4px; font-family: monospace;">{invitation_url}</p>
                    
                    <div class="warning-box">
                        <strong>⚠️ Important:</strong> This invitation link will expire in 7 days. Please accept the invitation and set your password before then.
                    </div>
                    
                    <h3>About AgriConnect</h3>
                    <p>AgriConnect is a comprehensive agricultural extension platform designed to connect farmers with agricultural services and support. As a {user_type_display}, you'll have access to:</p>
                    
                    <ul>
                        {"<li>Administrative tools and user management</li>" if user_type == "admin" else ""}
                        {"<li>Customer and farmer management</li>" if user_type == "eo" else ""}
                        <li>Communication and messaging tools</li>
                        <li>Agricultural resources and information</li>
                        <li>Reporting and analytics</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p><strong>AgriConnect Platform</strong></p>
                    <p>© 2025 AgriConnect. Empowering sustainable agriculture through digital innovation.</p>
                    <p>If you have any questions, please contact your administrator.</p>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Welcome to AgriConnect!
            
            Hello {full_name}!
            
            You have been invited to join AgriConnect as a {user_type_display} by {invited_by_name}.
            
            Your Account Details:
            Email: {email}
            Role: {user_type_display}
            
            To complete your account setup, please visit the following link to set your password:
            {invitation_url}
            
            IMPORTANT: This invitation link will expire in 7 days.
            
            About AgriConnect:
            AgriConnect is a comprehensive agricultural extension platform designed to connect farmers with agricultural services and support.
            
            If you have any questions, please contact your administrator.
            
            © 2025 AgriConnect Platform
            """
            
            message = MessageSchema(
                subject="Welcome to AgriConnect - Complete Your Account Setup",
                recipients=[email],
                body=html_content,
                alternative_body=text_content,
                subtype=MessageType.html
            )
            
            await self.fastmail.send_message(message)
            logger.info(f"Invitation email sent successfully to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send invitation email to {email}: {str(e)}")
            return False
    
    async def send_password_reset_email(
        self,
        email: EmailStr,
        full_name: str,
        reset_token: str
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
            reset_url = f"{self.protocol}://{self.web_domain}/reset-password/{reset_token}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Password Reset - AgriConnect</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
                        color: white;
                        padding: 30px 20px;
                        text-align: center;
                        border-radius: 8px 8px 0 0;
                    }}
                    .content {{
                        background: #ffffff;
                        padding: 30px 20px;
                        border: 1px solid #e5e7eb;
                        border-top: none;
                    }}
                    .footer {{
                        background: #f9fafb;
                        padding: 20px;
                        text-align: center;
                        border: 1px solid #e5e7eb;
                        border-top: none;
                        border-radius: 0 0 8px 8px;
                        color: #6b7280;
                        font-size: 14px;
                    }}
                    .cta-button {{
                        display: inline-block;
                        background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
                        color: white;
                        padding: 12px 30px;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: 600;
                        margin: 20px 0;
                    }}
                    .warning-box {{
                        background: #fef3cd;
                        border: 1px solid #f59e0b;
                        border-radius: 6px;
                        padding: 15px;
                        margin: 20px 0;
                        font-size: 14px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🔒 Password Reset</h1>
                    <p>AgriConnect Platform</p>
                </div>
                
                <div class="content">
                    <h2>Hello {full_name}!</h2>
                    
                    <p>You have requested to reset your password for your AgriConnect account.</p>
                    
                    <p>To reset your password, please click the button below:</p>
                    
                    <div style="text-align: center;">
                        <a href="{reset_url}" class="cta-button">Reset Password</a>
                    </div>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background: #f3f4f6; padding: 10px; border-radius: 4px; font-family: monospace;">{reset_url}</p>
                    
                    <div class="warning-box">
                        <strong>⚠️ Important:</strong> This reset link will expire in 1 hour. If you didn't request this password reset, please ignore this email.
                    </div>
                </div>
                
                <div class="footer">
                    <p><strong>AgriConnect Platform</strong></p>
                    <p>© 2025 AgriConnect. If you need help, please contact your administrator.</p>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Password Reset - AgriConnect
            
            Hello {full_name}!
            
            You have requested to reset your password for your AgriConnect account.
            
            To reset your password, please visit: {reset_url}
            
            IMPORTANT: This link will expire in 1 hour. If you didn't request this reset, please ignore this email.
            
            © 2025 AgriConnect Platform
            """
            
            message = MessageSchema(
                subject="Password Reset - AgriConnect",
                recipients=[email],
                body=html_content,
                alternative_body=text_content,
                subtype=MessageType.html
            )
            
            await self.fastmail.send_message(message)
            logger.info(f"Password reset email sent successfully to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {str(e)}")
            return False


# Global email service instance
email_service = EmailService()