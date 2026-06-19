"""Tenant management API — super-admin creates and manages organisations.

Each tenant is a completely isolated company/organisation:
  - own users, sessions, knowledge base, settings
  - own usage stats and billing counters
  - own API keys (stored in platform_secrets keyed by tenant slug)

Only super-admin (is_superuser=True) or platform admins can manage tenants.
Regular tenant-level admins can only read their own tenant.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLogModel,
    ChatMessageModel,
    ChatSessionModel,
    EscalationModel,
    KnowledgeDocumentModel,
    TenantModel,
    UserModel,
)
from app.db.session import get_db
from app.models.schemas import Principal
from app.security.auth import get_principal, require_roles

router = APIRouter(prefix="/tenants", tags=["tenants"])

PLAN_LIMITS = {
    "free":       {"max_users": 3,   "max_chat_sessions": 100,  "max_voice_minutes": 10},
    "starter":    {"max_users": 10,  "max_chat_sessions": 1000, "max_voice_minutes": 60},
    "pro":        {"max_users": 50,  "max_chat_sessions": 5000, "max_voice_minutes": 300},
    "enterprise": {"max_users": 500, "max_chat_sessions": 50000,"max_voice_minutes": 3000},
}

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")


def _tenant_to_dict(t: TenantModel) -> dict:
    return {
        "id": str(t.id),
        "slug": t.slug,
        "name": t.name,
        "admin_email": t.admin_email,
        "plan": t.plan,
        "status": t.status,
        "max_users": t.max_users,
        "max_chat_sessions": t.max_chat_sessions,
        "max_voice_minutes": t.max_voice_minutes,
        "settings": t.settings,
        "notes": t.notes,
        "trial_ends_at": t.trial_ends_at.isoformat() if t.trial_ends_at else None,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


# ── List all tenants (super-admin / platform admin) ───────────────────────────

@router.get("")
async def list_tenants(
    status: str | None = Query(None),
    plan: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset_val: int = Query(0, alias="offset", ge=0),
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    q = select(TenantModel)
    if status:
        q = q.where(TenantModel.status == status)
    if plan:
        q = q.where(TenantModel.plan == plan)
    q = q.order_by(TenantModel.created_at.desc()).offset(offset_val).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    count_q = select(func.count(TenantModel.id))
    if status:
        count_q = count_q.where(TenantModel.status == status)
    if plan:
        count_q = count_q.where(TenantModel.plan == plan)
    total = (await db.execute(count_q)).scalar_one_or_none() or 0

    return {"tenants": [_tenant_to_dict(r) for r in rows], "total": total}


# ── Get current user's own tenant ────────────────────────────────────────────

@router.get("/me/info")
async def get_my_tenant(
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the tenant of the currently authenticated user (no slug needed)."""
    slug = principal.tenant_id or "default"
    row = (await db.execute(
        select(TenantModel).where(TenantModel.slug == slug)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _tenant_to_dict(row)


# ── Get single tenant ─────────────────────────────────────────────────────────

@router.get("/{tenant_slug}")
async def get_tenant(
    tenant_slug: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = (await db.execute(
        select(TenantModel).where(TenantModel.slug == tenant_slug)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")
    # Tenant-level users can only view their own tenant
    if principal.tenant_id and principal.tenant_id != tenant_slug and "admin" not in (principal.roles or []):
        raise HTTPException(status_code=403, detail="Forbidden")
    return _tenant_to_dict(row)


# ── Create tenant ─────────────────────────────────────────────────────────────

@router.post("")
async def create_tenant(
    body: dict[str, Any] = Body(...),
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    slug = body.get("slug", "").strip().lower()
    name = body.get("name", "").strip()
    admin_email = body.get("admin_email", "").strip()
    plan = body.get("plan", "starter")

    if not slug or not _SLUG_RE.match(slug):
        raise HTTPException(status_code=422, detail="slug must be 3-64 lowercase letters/numbers/hyphens, not starting/ending with hyphen")
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if not admin_email or "@" not in admin_email:
        raise HTTPException(status_code=422, detail="valid admin_email is required")
    if plan not in PLAN_LIMITS:
        raise HTTPException(status_code=422, detail=f"plan must be one of: {', '.join(PLAN_LIMITS)}")

    # Uniqueness check
    existing = (await db.execute(
        select(TenantModel).where(TenantModel.slug == slug)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Tenant '{slug}' already exists")

    limits = PLAN_LIMITS[plan]
    tenant = TenantModel(
        id=uuid.uuid4(),
        slug=slug,
        name=name,
        admin_email=admin_email,
        plan=plan,
        status=body.get("status", "active"),
        max_users=body.get("max_users", limits["max_users"]),
        max_chat_sessions=body.get("max_chat_sessions", limits["max_chat_sessions"]),
        max_voice_minutes=body.get("max_voice_minutes", limits["max_voice_minutes"]),
        settings=body.get("settings", {}),
        notes=body.get("notes"),
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return _tenant_to_dict(tenant)


# ── Update tenant ─────────────────────────────────────────────────────────────

@router.patch("/{tenant_slug}")
async def update_tenant(
    tenant_slug: str,
    body: dict[str, Any] = Body(...),
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = (await db.execute(
        select(TenantModel).where(TenantModel.slug == tenant_slug)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")

    allowed = {"name", "admin_email", "plan", "status", "max_users",
               "max_chat_sessions", "max_voice_minutes", "settings", "notes", "trial_ends_at"}
    for field, value in body.items():
        if field in allowed:
            setattr(row, field, value)

    # Auto-update plan limits when plan changes
    if "plan" in body and body["plan"] in PLAN_LIMITS:
        limits = PLAN_LIMITS[body["plan"]]
        if "max_users" not in body:
            row.max_users = limits["max_users"]
        if "max_chat_sessions" not in body:
            row.max_chat_sessions = limits["max_chat_sessions"]
        if "max_voice_minutes" not in body:
            row.max_voice_minutes = limits["max_voice_minutes"]

    await db.commit()
    await db.refresh(row)
    return _tenant_to_dict(row)


# ── Delete / suspend tenant ───────────────────────────────────────────────────

@router.delete("/{tenant_slug}")
async def delete_tenant(
    tenant_slug: str,
    hard_delete: bool = Query(False, description="Permanently delete (default: suspend)"),
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = (await db.execute(
        select(TenantModel).where(TenantModel.slug == tenant_slug)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if hard_delete:
        await db.delete(row)
        await db.commit()
        return {"deleted": True, "slug": tenant_slug}
    else:
        row.status = "suspended"
        await db.commit()
        return {"suspended": True, "slug": tenant_slug}


# ── Per-tenant live usage stats ───────────────────────────────────────────────

@router.get("/{tenant_slug}/stats")
async def tenant_stats(
    tenant_slug: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Live usage counters for a single tenant."""
    # Permission: admin sees all, tenant user sees only own
    if principal.tenant_id and principal.tenant_id != tenant_slug:
        if "admin" not in (principal.roles or []):
            raise HTTPException(status_code=403, detail="Forbidden")

    row = (await db.execute(
        select(TenantModel).where(TenantModel.slug == tenant_slug)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # User counts
    user_counts = await db.execute(
        select(UserModel.is_active, func.count(UserModel.id))
        .where(UserModel.tenant_id == tenant_slug)
        .group_by(UserModel.is_active)
    )
    uc = {bool(r[0]): r[1] for r in user_counts.all()}
    total_users = sum(uc.values())
    active_users = uc.get(True, 0)

    # Chat stats
    total_sessions = (await db.execute(
        select(func.count(ChatSessionModel.id)).where(ChatSessionModel.tenant_id == tenant_slug)
    )).scalar_one_or_none() or 0

    total_messages = (await db.execute(
        select(func.count(ChatMessageModel.id)).join(
            ChatSessionModel, ChatMessageModel.session_id == ChatSessionModel.id
        ).where(ChatSessionModel.tenant_id == tenant_slug)
    )).scalar_one_or_none() or 0

    # Escalations
    total_escalations = (await db.execute(
        select(func.count(EscalationModel.id)).where(EscalationModel.tenant_id == tenant_slug)
    )).scalar_one_or_none() or 0

    # Knowledge docs
    total_docs = (await db.execute(
        select(func.count(KnowledgeDocumentModel.id)).where(
            KnowledgeDocumentModel.tenant_id == tenant_slug
        )
    )).scalar_one_or_none() or 0

    # Utilisation percentages
    def pct(used: int, limit: int) -> float:
        return round(used / limit * 100, 1) if limit > 0 else 0.0

    return {
        "tenant": _tenant_to_dict(row),
        "usage": {
            "users": {
                "total": total_users,
                "active": active_users,
                "limit": row.max_users,
                "utilisation_pct": pct(total_users, row.max_users),
            },
            "chat_sessions": {
                "total": total_sessions,
                "limit": row.max_chat_sessions,
                "utilisation_pct": pct(total_sessions, row.max_chat_sessions),
            },
            "messages": {"total": total_messages},
            "escalations": {"total": total_escalations},
            "knowledge_docs": {"total": total_docs},
        },
    }


# ── All tenants summary (for platform overview dashboard) ────────────────────

@router.get("/_summary/all")
async def all_tenants_summary(
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Aggregated usage across all tenants — platform owner view."""
    tenants = (await db.execute(select(TenantModel))).scalars().all()

    rows = []
    for t in tenants:
        user_count = (await db.execute(
            select(func.count(UserModel.id)).where(UserModel.tenant_id == t.slug)
        )).scalar_one_or_none() or 0

        session_count = (await db.execute(
            select(func.count(ChatSessionModel.id)).where(ChatSessionModel.tenant_id == t.slug)
        )).scalar_one_or_none() or 0

        rows.append({
            "slug": t.slug,
            "name": t.name,
            "plan": t.plan,
            "status": t.status,
            "user_count": user_count,
            "session_count": session_count,
            "created_at": t.created_at.isoformat(),
        })

    return {
        "tenants": rows,
        "totals": {
            "total_tenants": len(rows),
            "active_tenants": sum(1 for r in rows if r["status"] == "active"),
            "total_users": sum(r["user_count"] for r in rows),
            "total_sessions": sum(r["session_count"] for r in rows),
        },
    }
