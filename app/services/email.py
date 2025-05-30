import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending transactional emails"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_from = settings.SMTP_FROM
        self.smtp_tls = settings.SMTP_TLS
        self.smtp_ssl = settings.SMTP_SSL
        
        # Template configuration
        template_dir = Path(__file__).parent.parent / "templates" / "emails"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._send_email_sync,
            to_email,
            subject,
            html_content,
            text_content
        )
    
    def _send_email_sync(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email synchronously"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_from
            msg['To'] = to_email
            
            # Add text content
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            if self.smtp_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                if self.smtp_tls:
                    server.starttls()
            
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    async def send_verification_email(
        self,
        to_email: str,
        username: str,
        verification_token: str
    ) -> bool:
        """Send email verification email"""
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
        
        template = self.env.get_template("verification.html")
        html_content = template.render(
            username=username,
            verification_url=verification_url,
            app_name=settings.PROJECT_NAME
        )
        
        text_content = f"""
Hello {username},

Please verify your email address by clicking the link below:

{verification_url}

If you didn't create an account, please ignore this email.

Best regards,
{settings.PROJECT_NAME} Team
"""
        
        return await self.send_email(
            to_email=to_email,
            subject=f"Verify your {settings.PROJECT_NAME} account",
            html_content=html_content,
            text_content=text_content
        )
    
    async def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str
    ) -> bool:
        """Send password reset email"""
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        template = self.env.get_template("password_reset.html")
        html_content = template.render(
            username=username,
            reset_url=reset_url,
            app_name=settings.PROJECT_NAME
        )
        
        text_content = f"""
Hello {username},

You requested a password reset. Click the link below to reset your password:

{reset_url}

This link will expire in 1 hour.

If you didn't request this, please ignore this email.

Best regards,
{settings.PROJECT_NAME} Team
"""
        
        return await self.send_email(
            to_email=to_email,
            subject=f"Password reset for {settings.PROJECT_NAME}",
            html_content=html_content,
            text_content=text_content
        )
    
    async def send_welcome_email(
        self,
        to_email: str,
        username: str
    ) -> bool:
        """Send welcome email after successful registration"""
        template = self.env.get_template("welcome.html")
        html_content = template.render(
            username=username,
            app_name=settings.PROJECT_NAME,
            login_url=f"{settings.FRONTEND_URL}/login"
        )
        
        text_content = f"""
Welcome to {settings.PROJECT_NAME}, {username}!

Thank you for joining us. Your account has been successfully created.

You can now log in and start using our services.

Best regards,
{settings.PROJECT_NAME} Team
"""
        
        return await self.send_email(
            to_email=to_email,
            subject=f"Welcome to {settings.PROJECT_NAME}!",
            html_content=html_content,
            text_content=text_content
        )


# Singleton instance
email_service = EmailService()