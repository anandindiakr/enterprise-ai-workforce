"""System alert service — evaluates metric thresholds and sends email notifications.

Alert thresholds (configurable via environment variables):
    ALERT_ERROR_RATE_WARNING   default 5.0   (%)
    ALERT_ERROR_RATE_CRITICAL  default 15.0  (%)
    ALERT_SERVICE_DOWN_EMAIL   default True
    ALERT_EMAIL_TO             falls back to ESCALATION_EMAIL_TO

Emails use the same Resend / SMTP stack as the escalation service.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger

# ── Threshold defaults ────────────────────────────────────────────────────────

_THRESHOLDS: dict[str, float] = {
    "error_rate_warning":  float(os.getenv("ALERT_ERROR_RATE_WARNING",  "5.0")),
    "error_rate_critical": float(os.getenv("ALERT_ERROR_RATE_CRITICAL", "15.0")),
    "high_escalations":    float(os.getenv("ALERT_HIGH_ESCALATIONS",    "10")),
}

_ALERT_EMAIL_TO: str = (
    os.getenv("ALERT_EMAIL_TO")
    or os.getenv("ESCALATION_EMAIL_TO")
    or settings.escalation_email_to
    or ""
)


def get_thresholds() -> dict[str, float]:
    return dict(_THRESHOLDS)


def update_thresholds(new: dict[str, float]) -> dict[str, float]:
    _THRESHOLDS.update({k: v for k, v in new.items() if k in _THRESHOLDS})
    return dict(_THRESHOLDS)


# ── Core evaluation logic ─────────────────────────────────────────────────────

async def evaluate_and_fire(
    stats: dict[str, Any],
    db: AsyncSession,
    tenant_id: str = "default",
) -> list[dict]:
    """Compare *stats* against thresholds; persist + email any breaches.

    Returns the list of alert dicts that were fired in this call.
    """
    fired: list[dict] = []

    # 1. Error rate
    error_rate = float(stats.get("error_rate_pct", 0))
    if error_rate >= _THRESHOLDS["error_rate_critical"]:
        fired.append(await _fire(
            db=db, tenant_id=tenant_id, level="critical",
            title="Critical Error Rate",
            message=f"Platform error rate is {error_rate:.1f}% — exceeds critical threshold of {_THRESHOLDS['error_rate_critical']:.1f}%.",
            metric="error_rate_pct", metric_value=str(error_rate),
            threshold=str(_THRESHOLDS["error_rate_critical"]),
        ))
    elif error_rate >= _THRESHOLDS["error_rate_warning"]:
        fired.append(await _fire(
            db=db, tenant_id=tenant_id, level="warning",
            title="Elevated Error Rate",
            message=f"Platform error rate is {error_rate:.1f}% — exceeds warning threshold of {_THRESHOLDS['error_rate_warning']:.1f}%.",
            metric="error_rate_pct", metric_value=str(error_rate),
            threshold=str(_THRESHOLDS["error_rate_warning"]),
        ))

    # 2. Services down
    for svc in stats.get("services", []):
        if svc.get("status") == "down":
            fired.append(await _fire(
                db=db, tenant_id=tenant_id, level="critical",
                title=f"Service Down: {svc['name']}",
                message=f"{svc['name']} is unreachable. Details: {svc.get('details', 'N/A')}",
                metric=f"service.{svc['name'].lower().replace(' ', '_')}",
                metric_value="down", threshold="healthy",
            ))

    # 3. High escalation count today (proxy: active_chat_sessions as placeholder;
    #    you can wire real escalation count from analytics if desired)
    # (placeholder — extend as needed)

    return fired


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _fire(
    db: AsyncSession,
    tenant_id: str,
    level: str,
    title: str,
    message: str,
    metric: str | None = None,
    metric_value: str | None = None,
    threshold: str | None = None,
) -> dict:
    """Persist an alert and attempt to email it."""
    from app.db.models import SystemAlertModel

    email_to = _ALERT_EMAIL_TO
    email_sent = False
    if email_to:
        try:
            email_sent = await _send_alert_email(
                level=level, title=title, message=message,
                metric=metric, metric_value=metric_value, threshold=threshold,
                to_addr=email_to,
            )
        except Exception as exc:
            logger.warning("Alert email failed: {}", exc)

    alert = SystemAlertModel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        level=level,
        title=title,
        message=message,
        metric=metric,
        metric_value=metric_value,
        threshold=threshold,
        email_sent=email_sent,
        email_to=email_to or None,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    logger.info("System alert fired [{}] {}: {}", level.upper(), title, message)
    return {
        "id": str(alert.id),
        "level": level,
        "title": title,
        "message": message,
        "metric": metric,
        "metric_value": metric_value,
        "threshold": threshold,
        "email_sent": email_sent,
        "email_to": email_to or None,
        "created_at": alert.created_at.isoformat(),
    }


async def _send_alert_email(
    level: str,
    title: str,
    message: str,
    to_addr: str,
    metric: str | None = None,
    metric_value: str | None = None,
    threshold: str | None = None,
) -> bool:
    """Send alert via Resend (primary) or SMTP (fallback). Returns True on success."""
    color = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}.get(level, "#6b7280")
    icon  = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(level, "🔔")
    subject = f"{icon} [{level.upper()}] AlgoWorkforce Alert: {title}"

    html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:600px;margin:auto;background:#f9fafb;">
  <div style="background:{color};color:#fff;padding:20px;border-radius:8px 8px 0 0;">
    <h2 style="margin:0">{icon} {title}</h2>
    <p style="margin:4px 0 0;opacity:.85;font-size:13px">{level.upper()} — AlgoWorkforce Platform</p>
  </div>
  <div style="background:#fff;border:1px solid #e5e7eb;padding:24px;border-radius:0 0 8px 8px;">
    <p style="font-size:15px;color:#111827">{message}</p>
    <table style="width:100%;border-collapse:collapse;margin-top:16px;font-size:13px;">
      {"<tr><td style='font-weight:600;padding:6px 0;width:130px;color:#6b7280'>Metric</td><td style='color:#111827'>" + metric + "</td></tr>" if metric else ""}
      {"<tr><td style='font-weight:600;padding:6px 0;color:#6b7280'>Current Value</td><td style='color:" + color + ";font-weight:700'>" + str(metric_value) + "</td></tr>" if metric_value else ""}
      {"<tr><td style='font-weight:600;padding:6px 0;color:#6b7280'>Threshold</td><td style='color:#111827'>" + str(threshold) + "</td></tr>" if threshold else ""}
    </table>
    <div style="margin-top:20px;padding:12px;background:#f3f4f6;border-radius:6px;font-size:12px;color:#6b7280">
      <strong>Time:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}<br>
      This is an automated alert from AlgoWorkforce Platform. Log in to investigate.
    </div>
  </div>
</body>
</html>"""

    text_body = (
        f"[{level.upper()}] {title}\n\n"
        f"{message}\n\n"
        f"Metric: {metric or 'N/A'}\n"
        f"Value:  {metric_value or 'N/A'}\n"
        f"Threshold: {threshold or 'N/A'}\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
    )

    resend_key = settings.resend_api_key or os.getenv("RESEND_API_KEY", "")
    from_addr  = settings.email_from or "noreply@algoworkforce.com"

    if resend_key:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as sess:
                resp = await sess.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={"from": from_addr, "to": [to_addr], "subject": subject,
                          "html": html_body, "text": text_body},
                )
                if resp.status in (200, 201):
                    data = await resp.json()
                    logger.info("Alert email sent via Resend id={}", data.get("id"))
                    return True
                err = await resp.text()
                logger.warning("Resend alert email failed ({}): {}", resp.status, err)
        except Exception as exc:
            logger.warning("Resend alert exception: {}", exc)

    smtp_host = settings.smtp_host or os.getenv("SMTP_HOST", "")
    if smtp_host:
        try:
            import smtplib, ssl as _ssl
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = from_addr
            msg["To"]      = to_addr
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            ctx = _ssl.create_default_context()
            with smtplib.SMTP(smtp_host, int(settings.smtp_port or 587)) as srv:
                srv.ehlo()
                srv.starttls(context=ctx)
                srv.ehlo()
                if settings.smtp_user and settings.smtp_password:
                    srv.login(settings.smtp_user, settings.smtp_password)
                srv.sendmail(from_addr, [to_addr], msg.as_string())
            logger.info("Alert email sent via SMTP to {}", to_addr)
            return True
        except Exception as exc:
            logger.error("SMTP alert email failed: {}", exc)

    logger.warning("No email provider configured — alert email not sent for: {}", title)
    return False


# ── Manual test alert ─────────────────────────────────────────────────────────

async def send_test_alert(db: AsyncSession, tenant_id: str, email_to: str) -> dict:
    """Fire a test alert directly to *email_to*."""
    global _ALERT_EMAIL_TO
    orig = _ALERT_EMAIL_TO
    _ALERT_EMAIL_TO = email_to
    try:
        result = await _fire(
            db=db, tenant_id=tenant_id, level="info",
            title="Test Alert",
            message="This is a test alert from AlgoWorkforce System Monitoring. Email notifications are working correctly.",
            metric="manual_test", metric_value="1", threshold="N/A",
        )
    finally:
        _ALERT_EMAIL_TO = orig
    return result
