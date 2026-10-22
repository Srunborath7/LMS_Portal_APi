import asyncio
import html
import logging
import os
import smtplib
from email.message import EmailMessage

from app.core.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


def _send_gmail_sync(recipient: str, reset_url: str) -> None:
    sender = os.getenv("GMAIL_ADDRESS", "").strip()
    app_password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not sender or not app_password:
        raise ServiceUnavailable("Password reset email is not configured")

    message = EmailMessage()
    message["Subject"] = "Reset your LMS Portal password"
    message["From"] = sender
    message["To"] = recipient
    safe_reset_url = html.escape(reset_url, quote=True)
    message.set_content(
        "We received a request to reset your LMS Portal password.\n\n"
        "Use the link below within 30 minutes:\n\n"
        f"{reset_url}\n\n"
        "If you did not request a password reset, you can safely ignore this email."
    )
    message.add_alternative(
        f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background-color:#f3f5fa;font-family:Arial,Helvetica,sans-serif;color:#26304d;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f3f5fa;padding:36px 16px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background-color:#ffffff;border-radius:16px;overflow:hidden;">
          <tr><td style="background-color:#1E2A5A;padding:28px 36px;">
            <div style="font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#ffffff;font-weight:bold;">LMS Portal</div>
            <div style="height:4px;width:48px;background-color:#F2B134;margin-top:16px;"></div>
          </td></tr>
          <tr><td style="padding:36px;">
            <h1 style="margin:0 0 16px;color:#1E2A5A;font-size:25px;line-height:1.3;">Reset your password</h1>
            <p style="margin:0 0 24px;font-size:16px;line-height:1.6;color:#4b556b;">We received a request to reset the password for your LMS Portal account. Use the button below to choose a new password.</p>
            <table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td align="center" style="border-radius:8px;background-color:#F2B134;">
              <a href="{safe_reset_url}" style="display:inline-block;padding:14px 24px;color:#1E2A5A;text-decoration:none;font-size:15px;font-weight:bold;border-radius:8px;">Reset password</a>
            </td></tr></table>
            <p style="margin:26px 0 8px;font-size:13px;line-height:1.6;color:#667085;">This link expires in 30 minutes and can only be used once.</p>
            <p style="margin:0;font-size:13px;line-height:1.6;color:#667085;">If the button doesn’t work, copy this link into your browser:</p>
            <p style="margin:8px 0 0;word-break:break-all;font-size:12px;line-height:1.6;"><a href="{safe_reset_url}" style="color:#2a3a7a;">{safe_reset_url}</a></p>
            <hr style="border:0;border-top:1px solid #e7eaf1;margin:28px 0 20px;">
            <p style="margin:0;font-size:13px;line-height:1.6;color:#667085;">If you didn’t request this change, you can safely ignore this email. Your password will remain unchanged.</p>
          </td></tr>
          <tr><td style="padding:18px 36px;background-color:#f8f9fc;color:#7b8499;font-size:12px;line-height:1.5;">LMS Portal · Account security</td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>
""",
        subtype="html",
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(sender, app_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.exception("Gmail SMTP password reset delivery failed")
        raise ServiceUnavailable("Could not send password reset email") from exc


async def send_password_reset_email(recipient: str, reset_url: str) -> None:
    await asyncio.to_thread(_send_gmail_sync, recipient, reset_url)
