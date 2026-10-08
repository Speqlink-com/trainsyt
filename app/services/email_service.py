"""Zoho SMTP delivery for authentication workflows."""

import asyncio
import logging
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from time import sleep

from app.core.core import settings
from app.services.email_templates import (
    password_reset_code_email,
    temporary_password_email,
    training_reminder_email,
)

logger = logging.getLogger(__name__)


class EmailService:
    """Deliver branded security emails through Zoho SMTP."""

    def _message(self, to_email: str, subject: str, html: str, text: str) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = subject
        sender = settings.EMAIL_FROM or settings.ZOHO_EMAIL or "no-reply@trainsyt.local"
        message["From"] = formataddr((settings.EMAIL_FROM_NAME, sender))
        message["To"] = to_email
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(
            domain=(settings.ZOHO_EMAIL or "trainsyt.local").split("@")[-1]
        )
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        return message

    def _send_sync(self, message: EmailMessage) -> None:
        password = (
            settings.ZOHO_APP_PASSWORD.get_secret_value()
            if settings.ZOHO_APP_PASSWORD
            else ""
        )
        tls_context = ssl.create_default_context()
        for attempt in range(2):
            try:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                    server.ehlo()
                    if settings.SMTP_STARTTLS:
                        server.starttls(context=tls_context)
                        server.ehlo()
                    server.login(settings.ZOHO_EMAIL or "", password)
                    server.send_message(message)
                return
            except smtplib.SMTPResponseException as exc:
                if attempt or not 400 <= exc.smtp_code < 500:
                    raise
                sleep(1)

    async def send(self, to_email: str, subject: str, html: str, text: str) -> bool:
        if settings.EMAIL_DELIVERY_MODE == "console":
            logger.info("Development email to %s: %s", to_email, subject)
            return True
        if not settings.smtp_configured:
            logger.error("Zoho app-password credentials are not configured; email to %s was not sent", to_email)
            return False
        try:
            message = self._message(to_email, subject, html, text)
            await asyncio.to_thread(self._send_sync, message)
            logger.info("Email accepted by Zoho SMTP for %s", to_email)
            return True
        except (OSError, smtplib.SMTPException):
            logger.exception("Zoho SMTP delivery failed for %s", to_email)
            return False

    async def send_temporary_password(
        self,
        *,
        email: str,
        full_name: str,
        temporary_password: str,
    ) -> bool:
        subject, html, text = temporary_password_email(
            email=email,
            full_name=full_name,
            temporary_password=temporary_password,
        )
        return await self.send(email, subject, html, text)

    async def send_password_reset_code(
        self,
        *,
        email: str,
        full_name: str,
        code: str,
    ) -> bool:
        subject, html, text = password_reset_code_email(full_name=full_name, code=code)
        return await self.send(email, subject, html, text)

    async def send_training_reminder(
        self,
        *,
        email: str,
        full_name: str,
        training_title: str,
        scheduled_at: datetime,
        location: str,
        public_code: str,
        is_trainer: bool,
    ) -> bool:
        subject, html, text = training_reminder_email(
            full_name=full_name,
            training_title=training_title,
            scheduled_at=scheduled_at,
            location=location,
            public_code=public_code,
            is_trainer=is_trainer,
        )
        return await self.send(email, subject, html, text)


email_service = EmailService()
