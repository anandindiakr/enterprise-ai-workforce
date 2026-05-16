"""Audit log read-only API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.db.crud import list_audit_logs
from app.db.session import get_db
from app.models.schemas import Principal
from app.security.auth import require_roles

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
@router.get("/")
async def get_audit_logs(
    user_id: str | None = Query(None),
    action: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require_roles("admin")),
    db=Depends(get_db),
) -> dict:
    """List audit log entries. Admin-only."""
    logs = await list_audit_logs(
        db,
        tenant_id=principal.tenant_id or "default",
        user_id=user_id,
        action=action,
        skip=skip,
        limit=limit,
    )
    return {
        "logs": [
            {
                "id": str(log.id),
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "ip_address": log.ip_address,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": len(logs),
    }
