"""Email service for sending password reset emails."""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self):
        self.settings = get_settings()

    def _is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(
            self.settings.smtp_host
            and self.settings.smtp_user
            and self.settings.smtp_password
        )

    async def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str,
    ) -> bool:
        """Send password reset email.

        Args:
            to_email: Recipient email address
            username: User's username for personalization
            reset_token: Password reset token

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self._is_configured():
            logger.warning("Email service not configured, skipping email send")
            return False

        reset_link = f"{self.settings.frontend_url}/reset-password?token={reset_token}"

        subject = "【YueenEcoMind-AI】密码重置请求"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #0B1727 0%, #1E6F9F 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 12px 12px 0 0;
        }}
        .content {{
            background: #f9fafb;
            padding: 30px;
            border: 1px solid #e5e7eb;
            border-top: none;
        }}
        .button {{
            display: inline-block;
            background: #0B1727;
            color: white !important;
            padding: 14px 32px;
            text-decoration: none;
            border-radius: 50px;
            font-weight: 500;
            margin: 20px 0;
        }}
        .footer {{
            background: #f3f4f6;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            border-radius: 0 0 12px 12px;
            border: 1px solid #e5e7eb;
            border-top: none;
        }}
        .warning {{
            background: #fef3c7;
            border: 1px solid #f59e0b;
            border-radius: 8px;
            padding: 12px;
            margin: 16px 0;
            font-size: 14px;
            color: #92400e;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 24px;">YueenEcoMind-AI</h1>
        <p style="margin: 8px 0 0 0; opacity: 0.9;">智慧环保中台</p>
    </div>
    <div class="content">
        <h2 style="margin-top: 0;">您好，{username}！</h2>
        <p>我们收到了重置您账户密码的请求。点击下方按钮设置新密码：</p>
        <div style="text-align: center;">
            <a href="{reset_link}" class="button">重置密码</a>
        </div>
        <p>或者复制以下链接到浏览器打开：</p>
        <p style="background: #e5e7eb; padding: 12px; border-radius: 8px; word-break: break-all; font-size: 14px;">
            {reset_link}
        </p>
        <div class="warning">
            ⚠️ 此链接将在 {self.settings.password_reset_expire_minutes} 分钟后失效。如果您没有请求重置密码，请忽略此邮件。
        </div>
    </div>
    <div class="footer">
        <p>此邮件由 YueenEcoMind-AI 系统自动发送，请勿直接回复。</p>
        <p>© 2024 YueenEcoMind-AI. All rights reserved.</p>
    </div>
</body>
</html>
"""

        text_content = f"""
您好，{username}！

我们收到了重置您账户密码的请求。

请点击以下链接重置密码（{self.settings.password_reset_expire_minutes}分钟内有效）：
{reset_link}

如果您没有请求重置密码，请忽略此邮件。

---
YueenEcoMind-AI 智慧环保中台
"""

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email or self.settings.smtp_user}>"
            msg["To"] = to_email

            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            if self.settings.smtp_use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    context=context
                ) as server:
                    server.login(self.settings.smtp_user, self.settings.smtp_password)
                    server.sendmail(
                        self.settings.smtp_from_email or self.settings.smtp_user,
                        to_email,
                        msg.as_string()
                    )
            else:
                with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                    server.starttls()
                    server.login(self.settings.smtp_user, self.settings.smtp_password)
                    server.sendmail(
                        self.settings.smtp_from_email or self.settings.smtp_user,
                        to_email,
                        msg.as_string()
                    )

            logger.info(f"Password reset email sent to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send password reset email to {to_email}: {e}")
            return False


# Singleton instance
email_service = EmailService()
