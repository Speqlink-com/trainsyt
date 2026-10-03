"""Transactional email delivery for authentication workflows."""

import asyncio
import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.core import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Send branded security emails through the configured SMTP account."""

    def _message(self, to_email: str, subject: str, content: str, text: str) -> MIMEMultipart:
        document = f"""
        <!doctype html>
        <html>
          <body style="margin:0;background:#f5f6f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:#171d25">
            <div style="max-width:600px;margin:32px auto;background:#ffffff;border:1px solid #e0e5ec;border-radius:14px;overflow:hidden">
              <div style="padding:28px 36px;background:#641329;color:#ffffff">
                <h1 style="margin:0;font-size:24px">Jubilee Learning Hub</h1>
                <p style="margin:7px 0 0;color:#ead9dd">Workforce learning and compliance</p>
              </div>
              <div style="padding:36px">{content}</div>
              <div style="padding:20px 36px;background:#f7f8fa;color:#697386;font-size:12px">
                This is an automated security message. Never share a password or verification code.
              </div>
            </div>
          </body>
        </html>
        """
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>"
        message["To"] = to_email
        message.attach(MIMEText(text, "plain", "utf-8"))
        message.attach(MIMEText(document, "html", "utf-8"))
        return message

    def _send_sync(self, message: MIMEMultipart) -> None:
        password = settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else ""
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                server.login(settings.SMTP_USER or "", password)
                server.send_message(message)
            return

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            server.login(settings.SMTP_USER or "", password)
            server.send_message(message)

    async def send(self, to_email: str, subject: str, content: str, text: str) -> bool:
        if not settings.smtp_configured:
            logger.error("SMTP is not configured; email to %s was not sent", to_email)
            return False
        try:
            message = self._message(to_email, subject, content, text)
            await asyncio.to_thread(self._send_sync, message)
            logger.info("Authentication email accepted by SMTP for %s", to_email)
            return True
        except Exception:
            logger.exception("Authentication email delivery failed for %s", to_email)
            return False

    async def send_temporary_password(
        self,
        *,
        email: str,
        full_name: str,
        temporary_password: str,
    ) -> bool:
        safe_name = html.escape(full_name)
        safe_email = html.escape(email)
        safe_password = html.escape(temporary_password)
        sign_in_url = html.escape(settings.FRONTEND_URL.rstrip("/") + "/auth/login")
        content = f"""
          <p>Hello {safe_name},</p>
          <p>An administrator has created your Jubilee Learning Hub account.</p>
          <div style="margin:24px 0;padding:20px;background:#f7ecef;border-left:4px solid #9b1b36;border-radius:8px">
            <p style="margin:0 0 10px"><strong>Email:</strong> {safe_email}</p>
            <p style="margin:0"><strong>Temporary password:</strong> <code style="font-size:15px">{safe_password}</code></p>
          </div>
          <p><a href="{sign_in_url}" style="display:inline-block;padding:12px 20px;background:#9b1b36;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">Sign in securely</a></p>
          <p>This password is temporary. You will be required to replace it immediately after signing in.</p>
        """
        text = (
            f"Hello {full_name},\n\nYour Jubilee Learning Hub account is ready.\n"
            f"Email: {email}\nTemporary password: {temporary_password}\n\n"
            f"Sign in at {settings.FRONTEND_URL.rstrip('/')}/auth/login. "
            "You must change this password immediately after signing in."
        )
        return await self.send(email, "Your Jubilee Learning Hub account", content, text)

    async def send_password_reset_code(
        self,
        *,
        email: str,
        full_name: str,
        code: str,
    ) -> bool:
        safe_name = html.escape(full_name)
        content = f"""
          <p>Hello {safe_name},</p>
          <p>Use this one-time code to reset your Jubilee Learning Hub password:</p>
          <div style="margin:24px 0;padding:20px;text-align:center;border:2px solid #9b1b36;border-radius:10px;font-size:32px;font-weight:700;letter-spacing:8px">{html.escape(code)}</div>
          <p>The code expires in {settings.OTP_EXPIRE_MINUTES} minutes and can only be used once.</p>
          <p>If you did not request this reset, you can ignore this message.</p>
        """
        text = (
            f"Hello {full_name},\n\nYour Jubilee Learning Hub password reset code is {code}. "
            f"It expires in {settings.OTP_EXPIRE_MINUTES} minutes."
        )
        return await self.send(email, "Reset your Jubilee Learning Hub password", content, text)


email_service = EmailService()
