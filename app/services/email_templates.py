"""Branded HTML and plain-text templates for authentication emails."""

from datetime import UTC, datetime
from html import escape
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from app.core.core import settings


def _layout(
    title: str,
    preview: str,
    content: str,
    footer: str = "This is an automated security message. Never share a password or verification code.",
) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:#f5f6f8;font-family:Arial,sans-serif;color:#171d25">
<div style="display:none;max-height:0;overflow:hidden">{escape(preview)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border:1px solid #e0e5ec;border-radius:14px;overflow:hidden">
<tr><td style="padding:28px 32px;background:#641329;color:#fff"><div style="font-size:24px;font-weight:800">Jubilee Learning Hub</div><div style="margin-top:7px;color:#ead9dd">Workforce learning and compliance</div></td></tr>
<tr><td style="padding:32px"><h1 style="margin:0 0 16px;font-size:24px;line-height:1.3">{escape(title)}</h1>{content}</td></tr>
<tr><td style="padding:20px 32px;background:#f7f8fa;color:#697386;font-size:12px;line-height:1.6">{escape(footer)}</td></tr>
</table></td></tr></table></body></html>"""


def temporary_password_email(
    *,
    email: str,
    full_name: str,
    temporary_password: str,
) -> tuple[str, str, str]:
    sign_in_url = settings.FRONTEND_URL.rstrip("/") + "/auth/login"
    content = f"""<p style="margin:0 0 18px;color:#475569;line-height:1.6">Hello {escape(full_name)},</p>
<p style="margin:0 0 20px;color:#475569;line-height:1.6">An administrator has created your Jubilee Learning Hub account.</p>
<div style="margin:24px 0;padding:20px;background:#f7ecef;border-left:4px solid #9b1b36;border-radius:8px">
<p style="margin:0 0 10px"><strong>Email:</strong> {escape(email)}</p>
<p style="margin:0"><strong>Temporary password:</strong> <code style="font-size:15px">{escape(temporary_password)}</code></p></div>
<p style="margin:0 0 22px"><a href="{escape(sign_in_url)}" style="display:inline-block;padding:13px 22px;background:#9b1b36;color:#fff;text-decoration:none;border-radius:8px;font-weight:700">Sign in securely</a></p>
<p style="margin:0;color:#64748b;font-size:13px;line-height:1.6">You must replace this temporary password immediately after signing in.</p>"""
    text = (
        f"Hello {full_name},\n\nYour Jubilee Learning Hub account is ready.\n"
        f"Email: {email}\nTemporary password: {temporary_password}\n\n"
        f"Sign in at {sign_in_url}. You must change this password immediately after signing in."
    )
    return (
        "Your Jubilee Learning Hub account",
        _layout("Your account is ready", "Your Jubilee Learning Hub account is ready", content),
        text,
    )


def password_reset_code_email(*, full_name: str, code: str) -> tuple[str, str, str]:
    content = f"""<p style="margin:0 0 20px;color:#475569;line-height:1.6">Hello {escape(full_name)},</p>
<p style="margin:0 0 20px;color:#475569;line-height:1.6">Use this one-time code to reset your Jubilee Learning Hub password.</p>
<div style="padding:18px;text-align:center;background:#f7ecef;border:2px solid #9b1b36;border-radius:10px;font-size:32px;font-weight:800;letter-spacing:8px;color:#641329">{escape(code)}</div>
<p style="margin:20px 0 0;color:#64748b;font-size:13px;line-height:1.6">The code expires in {settings.OTP_EXPIRE_MINUTES} minutes and can only be used once. If you did not request it, you can safely ignore this email.</p>"""
    text = (
        f"Hello {full_name},\n\nYour Jubilee Learning Hub password reset code is {code}. "
        f"It expires in {settings.OTP_EXPIRE_MINUTES} minutes."
    )
    return (
        "Reset your Jubilee Learning Hub password",
        _layout("Reset your password", "Your password reset code", content),
        text,
    )


def training_reminder_email(
    *,
    full_name: str,
    training_title: str,
    scheduled_at: datetime,
    location: str,
    public_code: str,
    is_trainer: bool,
) -> tuple[str, str, str]:
    local_time = scheduled_at.replace(tzinfo=UTC).astimezone(ZoneInfo(settings.APP_TIMEZONE))
    formatted_time = local_time.strftime("%A, %d %B %Y at %H:%M %Z")
    join_url = (
        settings.FRONTEND_URL.rstrip("/")
        + "/attendance/check-in?"
        + urlencode({"training": public_code})
    )
    role_message = (
        "You are facilitating this programme."
        if is_trainer
        else "You are registered for this programme."
    )
    content = f"""<p style="margin:0 0 18px;color:#475569;line-height:1.6">Hello {escape(full_name)},</p>
<p style="margin:0 0 20px;color:#475569;line-height:1.6">{escape(role_message)} It starts in approximately one hour.</p>
<div style="margin:24px 0;padding:20px;background:#f7ecef;border-left:4px solid #9b1b36;border-radius:8px">
<p style="margin:0 0 10px"><strong>Programme:</strong> {escape(training_title)}</p>
<p style="margin:0 0 10px"><strong>Time:</strong> {escape(formatted_time)}</p>
<p style="margin:0"><strong>Location / meeting link:</strong> {escape(location)}</p></div>
<p style="margin:0 0 22px"><a href="{escape(join_url)}" style="display:inline-block;padding:13px 22px;background:#9b1b36;color:#fff;text-decoration:none;border-radius:8px;font-weight:700">Open programme</a></p>
<p style="margin:0;color:#64748b;font-size:13px;line-height:1.6">Attendance becomes available at the scheduled meeting time.</p>"""
    text = (
        f"Hello {full_name},\n\n{role_message} It starts in approximately one hour.\n"
        f"Programme: {training_title}\nTime: {formatted_time}\n"
        f"Location / meeting link: {location}\nOpen programme: {join_url}\n\n"
        "Attendance becomes available at the scheduled meeting time."
    )
    return (
        f"Reminder: {training_title} starts in one hour",
        _layout(
            "Your training starts soon",
            f"{training_title} starts in one hour",
            content,
            "This is an automated Jubilee Learning Hub training reminder.",
        ),
        text,
    )
