"""Escalation management API."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.db.crud import (
    create_escalation,
    list_escalations,
    resolve_escalation,
    write_audit_log,
)
from app.db.session import get_db
from app.models.schemas import Principal
from app.security.auth import get_principal

router = APIRouter(prefix="/escalations", tags=["escalations"])


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class EscalationCreate(BaseModel):
    session_id: str | None = None
    department: str = "reception"
    reason: str
    priority: str = "normal"  # low / normal / high / urgent
    metadata: dict[str, Any] = {}


class EscalationResolve(BaseModel):
    resolution_notes: str | None = None
    assigned_to: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_escalation_endpoint(
    body: EscalationCreate,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Create a new escalation and trigger an async notification."""
    esc = await create_escalation(
        db,
        session_id=body.session_id,
        tenant_id=principal.tenant_id or "default",
        user_id=principal.user_id,
        department=body.department,
        reason=body.reason,
        priority=body.priority,
        metadata=body.metadata,
    )

    # Fire-and-forget notification — try Celery first, fall back to asyncio task
    esc_payload = {
        "department": esc.department,
        "priority": esc.priority,
        "reason": esc.reason,
        "user_id": esc.user_id,
        "session_id": str(esc.session_id) if esc.session_id else None,
    }
    _dispatched = False
    try:
        from app.workers.tasks import send_escalation_notification
        send_escalation_notification.delay(str(esc.id), esc_payload)
        _dispatched = True
    except Exception:  # noqa: BLE001
        pass  # Celery not running — fall through to asyncio background task

    if not _dispatched:
        import asyncio
        from app.services.notification_service import send_escalation_email
        asyncio.create_task(send_escalation_email(str(esc.id), esc_payload))

    await write_audit_log(
        db,
        tenant_id=principal.tenant_id or "default",
        user_id=principal.user_id,
        action="escalation.create",
        resource_type="escalation",
        resource_id=str(esc.id),
        details={"department": esc.department, "priority": esc.priority},
    )

    return _esc_dict(esc)


@router.get("")
async def list_escalations_endpoint(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """List escalations for the calling principal's tenant."""
    escs = await list_escalations(
        db,
        tenant_id=principal.tenant_id or "default",
        status=status_filter,
        skip=skip,
        limit=limit,
    )
    return {"escalations": [_esc_dict(e) for e in escs], "total": len(escs)}


@router.get("/{escalation_id}")
async def get_escalation_endpoint(
    escalation_id: str,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Get a single escalation."""
    from sqlalchemy import select
    from app.db.models import EscalationModel
    try:
        eid = uuid.UUID(escalation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid escalation ID")

    result = await db.execute(
        select(EscalationModel).where(EscalationModel.id == eid)
    )
    esc = result.scalar_one_or_none()
    if esc is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return _esc_dict(esc)


@router.patch("/{escalation_id}/resolve")
async def resolve_escalation_endpoint(
    escalation_id: str,
    body: EscalationResolve,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Resolve an open escalation."""
    from sqlalchemy import select
    from app.db.models import EscalationModel
    try:
        eid = uuid.UUID(escalation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid escalation ID")

    result = await db.execute(
        select(EscalationModel).where(EscalationModel.id == eid)
    )
    esc = result.scalar_one_or_none()
    if esc is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if esc.status == "resolved":
        raise HTTPException(status_code=409, detail="Already resolved")

    esc = await resolve_escalation(
        db, esc,
        resolution_notes=body.resolution_notes,
        assigned_to=body.assigned_to,
    )
    await write_audit_log(
        db,
        tenant_id=principal.tenant_id or "default",
        user_id=principal.user_id,
        action="escalation.resolve",
        resource_type="escalation",
        resource_id=str(esc.id),
        details={"assigned_to": esc.assigned_to},
    )
    return _esc_dict(esc)


# ─────────────────────────────────────────────────────────────────────────────
# Serialiser
# ─────────────────────────────────────────────────────────────────────────────

def _esc_dict(esc: Any) -> dict:
    return {
        "id": str(esc.id),
        "session_id": str(esc.session_id) if esc.session_id else None,
        "tenant_id": esc.tenant_id,
        "user_id": esc.user_id,
        "department": esc.department,
        "reason": esc.reason,
        "priority": esc.priority,
        "status": esc.status,
        "assigned_to": esc.assigned_to,
        "resolution_notes": esc.resolution_notes,
        "created_at": esc.created_at.isoformat(),
        "resolved_at": esc.resolved_at.isoformat() if esc.resolved_at else None,
    }
