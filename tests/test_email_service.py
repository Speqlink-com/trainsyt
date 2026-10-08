"""Email transport and template behavior."""

from datetime import datetime

from app.services.email_service import email_service
from app.services.email_templates import temporary_password_email, training_reminder_email


async def test_console_delivery_does_not_open_smtp(monkeypatch) -> None:
    def unexpected_smtp_call(*_args, **_kwargs) -> None:
        raise AssertionError("Console delivery must not open an SMTP connection")

    monkeypatch.setattr(email_service, "_send_sync", unexpected_smtp_call)

    sent = await email_service.send(
        "user@example.com",
        "Security message",
        "<p>Security message</p>",
        "Security message",
    )

    assert sent is True


def test_temporary_password_template_escapes_user_content() -> None:
    subject, html, text = temporary_password_email(
        email="person@example.com",
        full_name="<Example User>",
        temporary_password="Temp<&Password123!",
    )

    assert subject == "Your Jubilee Learning Hub account"
    assert "&lt;Example User&gt;" in html
    assert "Temp&lt;&amp;Password123!" in html
    assert "<Example User>" not in html
    assert "person@example.com" in text


def test_training_reminder_contains_local_time_and_programme_link() -> None:
    subject, html, text = training_reminder_email(
        full_name="Example Participant",
        training_title="Compliance & Conduct",
        scheduled_at=datetime(2026, 10, 8, 11, 0),
        location="https://meet.example.com/secure-room",
        public_code="public-code",
        is_trainer=False,
    )

    assert "starts in one hour" in subject
    assert "14:00 EAT" in text
    assert "training=public-code" in text
    assert "Compliance &amp; Conduct" in html
