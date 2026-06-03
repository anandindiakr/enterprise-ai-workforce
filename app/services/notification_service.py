"""Email notification service (Resend → SMTP fallback)."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.core.config import settings
from app.core.logging import logger


async def send_escalation_email(
    escalation_id: str,
    escalation_data: dict[str, Any],
) -> dict[str, Any]:
    """Notify the on-call team about a new escalation.

    Tries Resend HTTP API first, then SMTP fallback.
    """
    subject = (
        f"[{escalation_data.get('priority', 'normal').upper()}] "
        f"Escalation in {escalation_data.get('department', 'unknown')} — {escalation_id[:8]}"
    )
    body_html = _build_escalation_html(escalation_id, escalation_data)
    body_text = _build_escalation_text(escalation_id, escalation_data)

    to_addr = settings.escalation_email_to or os.getenv("ESCALATION_EMAIL_TO", "")
    if not to_addr:
        logger.warning("No ESCALATION_EMAIL_TO set; skipping email for escalation {}", escalation_id)
        return {"sent": False, "reason": "no_recipient"}

    # Try Resend
    resend_key = settings.resend_api_key or os.getenv("RESEND_API_KEY", "")
    if resend_key:
        try:
            import aiohttp  # type: ignore
            async with aiohttp.ClientSession() as sess:
                resp = await sess.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={
                        "from": settings.email_from or "noreply@workforce.ai",
                        "to": [to_addr],
                        "subject": subject,
                        "html": body_html,
                        "text": body_text,
                    },
                )
                if resp.status in (200, 201):
                    data = await resp.json()
                    logger.info("Escalation email sent via Resend: {}", data.get("id"))
                    return {"sent": True, "provider": "resend", "message_id": data.get("id")}
                err = await resp.text()
                logger.warning("Resend failed ({}): {}", resp.status, err)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Resend exception: {}", exc)

    # SMTP fallback
    smtp_host = settings.smtp_host or os.getenv("SMTP_HOST", "")
    if smtp_host:
        try:
            _send_smtp(
                host=smtp_host,
                port=int(settings.smtp_port or 587),
                user=settings.smtp_user or "",
                password=settings.smtp_password or "",
                from_addr=settings.email_from or "noreply@workforce.ai",
                to_addr=to_addr,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            logger.info("Escalation email sent via SMTP to {}", to_addr)
            return {"sent": True, "provider": "smtp"}
        except Exception as exc:  # noqa: BLE001
            logger.error("SMTP send failed: {}", exc)
            return {"sent": False, "reason": str(exc)}

    return {"sent": False, "reason": "no_provider_configured"}


async def send_password_reset_email(to_email: str, reset_token: str) -> dict:
    """Send a password-reset link email."""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    reset_url    = f"{frontend_url}/reset-password?token={reset_token}"
    subject      = "AI Workforce Platform - Password Reset Request"
    body_html    = f"""<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; max-width:600px; margin:auto;">
  <div style="background:#4f46e5;color:#fff;padding:16px;border-radius:8px 8px 0 0;">
    <h2 style="margin:0">Password Reset Request</h2>
  </div>
  <div style="border:1px solid #e5e7eb;padding:20px;border-radius:0 0 8px 8px;">
    <p>You requested a password reset. Click the link below to set a new password:</p>
    <p><a href="{reset_url}" style="background:#4f46e5;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;display:inline-block;">Reset Password</a></p>
    <p style="color:#6b7280;font-size:13px">This link expires in 2 hours. If you did not request this, ignore this email.</p>
    <hr style="margin:16px 0">
    <p style="color:#6b7280;font-size:12px">AI Workforce Platform — automated notification</p>
  </div>
</body>
</html>"""
    body_text = f"Reset your password: {reset_url}\nLink expires in 2 hours."

    resend_key = settings.resend_api_key or os.getenv("RESEND_API_KEY", "")
    if resend_key:
        try:
            import aiohttp  # type: ignore
            async with aiohttp.ClientSession() as sess:
                resp = await sess.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={
                        "from": settings.email_from or "noreply@workforce.ai",
                        "to": [to_email],
                        "subject": subject,
                        "html": body_html,
                        "text": body_text,
                    },
                )
                if resp.status in (200, 201):
                    return {"sent": True, "provider": "resend"}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Resend password reset email failed: {}", exc)

    smtp_host = settings.smtp_host or os.getenv("SMTP_HOST", "")
    if smtp_host:
        try:
            _send_smtp(
                host=smtp_host,
                port=int(settings.smtp_port or 587),
                user=settings.smtp_user or "",
                password=settings.smtp_password or "",
                from_addr=settings.email_from or "noreply@workforce.ai",
                to_addr=to_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            return {"sent": True, "provider": "smtp"}
        except Exception as exc:  # noqa: BLE001
            logger.error("SMTP password reset email failed: {}", exc)
            return {"sent": False, "reason": str(exc)}

    logger.warning("No email provider configured; password reset email not sent to {}", to_email)
    return {"sent": False, "reason": "no_provider_configured"}


def _send_smtp(
    host: str,
    port: int,
    user: str,
    password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body_text: str,
    body_html: str,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_addr
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        if port in (587, 25):
            server.starttls(context=context)
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())


def _build_escalation_html(eid: str, data: dict) -> str:
    reason   = data.get("reason", "N/A")
    dept     = data.get("department", "N/A")
    priority = data.get("priority", "normal").upper()
    user_id  = data.get("user_id", "anonymous")
    color    = {"LOW": "#3b82f6", "NORMAL": "#f59e0b", "HIGH": "#ef4444", "URGENT": "#7c3aed"}.get(priority, "#6b7280")
    return f"""<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; max-width:600px; margin:auto;">
  <div style="background:{color};color:#fff;padding:16px;border-radius:8px 8px 0 0;">
    <h2 style="margin:0">⚠️ Escalation Alert — {priority}</h2>
  </div>
  <div style="border:1px solid #e5e7eb;padding:20px;border-radius:0 0 8px 8px;">
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="font-weight:bold;padding:6px 0;width:140px">Escalation ID</td><td>{eid}</td></tr>
      <tr><td style="font-weight:bold;padding:6px 0">Department</td><td>{dept}</td></tr>
      <tr><td style="font-weight:bold;padding:6px 0">Priority</td><td style="color:{color}">{priority}</td></tr>
      <tr><td style="font-weight:bold;padding:6px 0">User</td><td>{user_id}</td></tr>
      <tr><td style="font-weight:bold;padding:6px 0">Reason</td><td>{reason}</td></tr>
    </table>
    <hr style="margin:16px 0">
    <p style="color:#6b7280;font-size:12px">AI Workforce Platform — automated notification</p>
  </div>
</body>
</html>"""


def _build_escalation_text(eid: str, data: dict) -> str:
    return (
        f"ESCALATION ALERT\n"
        f"ID:         {eid}\n"
        f"Department: {data.get('department', 'N/A')}\n"
        f"Priority:   {data.get('priority', 'normal').upper()}\n"
        f"User:       {data.get('user_id', 'anonymous')}\n"
        f"Reason:     {data.get('reason', 'N/A')}\n"
    )
