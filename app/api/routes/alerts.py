"""Alert management endpoints — admin only."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SystemAlertModel
from app.db.session import get_db
from app.models.schemas import Principal
from app.security.auth import require_roles
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _alert_to_dict(a: SystemAlertModel) -> dict:
    return {
        "id": str(a.id),
        "level": a.level,
        "title": a.title,
        "message": a.message,
        "metric": a.metric,
        "metric_value": a.metric_value,
        "threshold": a.threshold,
        "email_sent": a.email_sent,
        "email_to": a.email_to,
        "resolved": a.resolved,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "created_at": a.created_at.isoformat(),
    }


# ── List recent alerts ────────────────────────────────────────────────────────

@router.get("")
async def list_alerts(
    level: str | None = Query(None, description="Filter by level: info|warning|critical"),
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    q = select(SystemAlertModel).where(
        SystemAlertModel.tenant_id == (principal.tenant_id or "default")
    )
    if level:
        q = q.where(SystemAlertModel.level == level)
    if resolved is not None:
        q = q.where(SystemAlertModel.resolved == resolved)
    q = q.order_by(desc(SystemAlertModel.created_at)).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return {
        "alerts": [_alert_to_dict(r) for r in rows],
        "total": len(rows),
    }


# ── Alert thresholds config ───────────────────────────────────────────────────

@router.get("/config")
async def get_alert_config(
    _: Principal = Depends(require_roles("admin")),
) -> dict:
    return {"thresholds": alert_service.get_thresholds()}


@router.put("/config")
async def update_alert_config(
    body: dict[str, float] = Body(...),
    _: Principal = Depends(require_roles("admin")),
) -> dict:
    updated = alert_service.update_thresholds(body)
    return {"thresholds": updated, "message": "Thresholds updated (in-memory — restart resets to env defaults)."}


# ── Send test alert ───────────────────────────────────────────────────────────

@router.post("/test")
async def send_test_alert(
    body: dict[str, Any] = Body(default={}),
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    email_to = body.get("email_to", "")
    if not email_to:
        raise HTTPException(status_code=422, detail="email_to is required")
    result = await alert_service.send_test_alert(
        db=db,
        tenant_id=principal.tenant_id or "default",
        email_to=email_to,
    )
    return result


# ── Resolve an alert ─────────────────────────────────────────────────────────

@router.patch("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await db.get(SystemAlertModel, alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    if row.tenant_id != (principal.tenant_id or "default"):
        raise HTTPException(status_code=403, detail="Forbidden")
    row.resolved = True
    row.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return _alert_to_dict(row)


# ── Delete alert ─────────────────────────────────────────────────────────────

@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await db.get(SystemAlertModel, alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    if row.tenant_id != (principal.tenant_id or "default"):
        raise HTTPException(status_code=403, detail="Forbidden")
    await db.delete(row)
    await db.commit()
    return {"deleted": True, "id": alert_id}
