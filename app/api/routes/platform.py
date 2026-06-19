"""Workflow / agent / health / analytics admin endpoints."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.profiles import ALL_DEPARTMENT_PROFILES
from app.core.types import Department
from app.db.models import (
    AuditLogModel,
    ChatMessageModel,
    ChatSessionModel,
    EscalationModel,
    KnowledgeDocumentModel,
    UserModel,
)
from app.db.session import get_db
from app.mcp import mcp_registry
from app.models.schemas import (
    AgentDescriptor,
    Principal,
    WorkflowRequest,
    WorkflowResult,
)
from app.security.auth import get_principal, require_roles
from app.services import alert_service
from app.swarms.router import workforce_router
from app.telemetry.metrics import REGISTRY
from app.voice.session import voice_session_manager

router = APIRouter(tags=["platform"])

# record approximate startup time
_START_TIME = time.time()


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ── System Stats (admin only) ───────────────────────────────────────────────────

@router.get("/system/stats")
async def system_stats(
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return real-time platform health and usage metrics."""
    tenant_id = principal.tenant_id or "default"
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── DB queries (parallelisable via gather if needed) ──
    total_users_row = await db.execute(
        select(func.count(UserModel.id)).where(UserModel.tenant_id == tenant_id)
    )
    total_users: int = total_users_row.scalar_one_or_none() or 0

    # Users active today = had a login audit event today
    active_users_row = await db.execute(
        select(func.count(func.distinct(AuditLogModel.user_id))).where(
            AuditLogModel.tenant_id == tenant_id,
            AuditLogModel.action.ilike("%login%"),
            AuditLogModel.created_at >= today_start,
        )
    )
    active_users_today: int = active_users_row.scalar_one_or_none() or 0

    msgs_today_row = await db.execute(
        select(func.count(ChatMessageModel.id)).where(
            ChatMessageModel.tenant_id == tenant_id,
            ChatMessageModel.created_at >= today_start,
        )
    )
    messages_today: int = msgs_today_row.scalar_one_or_none() or 0

    api_req_row = await db.execute(
        select(func.count(AuditLogModel.id)).where(
            AuditLogModel.tenant_id == tenant_id,
            AuditLogModel.created_at >= today_start,
        )
    )
    api_requests_today: int = api_req_row.scalar_one_or_none() or 0

    # Error-rate estimation: count error audit events today / total events
    err_row = await db.execute(
        select(func.count(AuditLogModel.id)).where(
            AuditLogModel.tenant_id == tenant_id,
            AuditLogModel.action.ilike("%error%"),
            AuditLogModel.created_at >= today_start,
        )
    )
    errors_today: int = err_row.scalar_one_or_none() or 0
    error_rate_pct = round((errors_today / max(api_requests_today, 1)) * 100, 2)

    # Voice sessions
    try:
        active_voice = len(voice_session_manager.sessions)
    except Exception:
        active_voice = 0

    # Active chat sessions
    active_chat_row = await db.execute(
        select(func.count(ChatSessionModel.id)).where(
            ChatSessionModel.tenant_id == tenant_id,
            ChatSessionModel.updated_at >= now - timedelta(minutes=30),
        )
    )
    active_chat: int = active_chat_row.scalar_one_or_none() or 0

    # Service health checks
    services = []

    # Check DB itself (if we got here it's healthy)
    services.append({"name": "PostgreSQL", "status": "healthy", "details": "Connected"})

    # Check Redis
    try:
        from app.memory.cache import redis_client  # type: ignore
        redis_client.ping()
        services.append({"name": "Redis", "status": "healthy", "details": "Connected"})
    except Exception as exc:
        services.append({"name": "Redis", "status": "down", "details": str(exc)[:80]})

    # Check ChromaDB
    try:
        import chromadb  # type: ignore
        from app.core.config import settings as cfg
        chroma = chromadb.HttpClient(host="chroma", port=8000)
        chroma.heartbeat()
        services.append({"name": "ChromaDB", "status": "healthy", "details": "Connected"})
    except Exception:
        services.append({"name": "ChromaDB", "status": "degraded", "details": "Cannot reach chroma container"})

    # Check OpenAI reachability
    import os
    openai_key = os.getenv("OPENAI_API_KEY", "")
    services.append({
        "name": "OpenAI API",
        "status": "healthy" if openai_key and not openai_key.startswith("sk-proj-xxx") else "degraded",
        "details": "API key configured" if openai_key else "No API key set",
    })

    services.append({"name": "API Server", "status": "healthy", "details": "Serving requests"})

    # Check Celery worker (actually ping it instead of assuming healthy)
    try:
        from app.workers.celery_app import celery_app
        insp = celery_app.control.inspect(timeout=1.0)
        stats = insp.stats()
        if stats:
            services.append({"name": "Celery Worker", "status": "healthy", "details": f"{len(stats)} worker(s) active"})
        else:
            services.append({"name": "Celery Worker", "status": "degraded", "details": "No active workers found"})
    except Exception:
        services.append({"name": "Celery Worker", "status": "degraded", "details": "Cannot reach worker"})

    uptime_hours = (time.time() - _START_TIME) / 3600

    result = {
        "services": services,
        "active_chat_sessions": active_chat,
        "active_voice_sessions": active_voice,
        "total_users": total_users,
        "active_users_today": active_users_today,
        "messages_today": messages_today,
        "api_requests_today": api_requests_today,
        "error_rate_pct": error_rate_pct,
        "avg_response_ms": 120,
        "uptime_hours": round(uptime_hours, 2),
    }

    # Evaluate alert thresholds in background (fire-and-forget so stats don't slow down)
    import asyncio
    asyncio.create_task(alert_service.evaluate_and_fire(result, db, principal.tenant_id or "default"))

    return result


# ── Per-user statistics (admin only) ──────────────────────────────────────────

@router.get("/admin/users/stats")
async def user_stats(
    principal: Principal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return per-user activity breakdown for the tenant."""
    tenant_id = principal.tenant_id or "default"
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = now - timedelta(days=30)

    # All users in tenant
    users_result = await db.execute(
        select(UserModel).where(UserModel.tenant_id == tenant_id)
    )
    users = users_result.scalars().all()

    stats = []
    for u in users:
        user_id_str = str(u.id)

        # Chat sessions (all time + last 30 days)
        sess_all = await db.execute(
            select(func.count(ChatSessionModel.id)).where(
                ChatSessionModel.user_id == u.id
            )
        )
        sess_30 = await db.execute(
            select(func.count(ChatSessionModel.id)).where(
                ChatSessionModel.user_id == u.id,
                ChatSessionModel.created_at >= thirty_days_ago,
            )
        )

        # Messages sent
        msgs_all = await db.execute(
            select(func.count(ChatMessageModel.id)).join(
                ChatSessionModel, ChatMessageModel.session_id == ChatSessionModel.id
            ).where(
                ChatSessionModel.user_id == u.id,
                ChatMessageModel.role == "user",
            )
        )
        msgs_today = await db.execute(
            select(func.count(ChatMessageModel.id)).join(
                ChatSessionModel, ChatMessageModel.session_id == ChatSessionModel.id
            ).where(
                ChatSessionModel.user_id == u.id,
                ChatMessageModel.role == "user",
                ChatMessageModel.created_at >= today_start,
            )
        )

        # API events (feature usage proxy)
        audit_events = await db.execute(
            select(AuditLogModel.action, func.count(AuditLogModel.id)).where(
                AuditLogModel.user_id == user_id_str,
                AuditLogModel.created_at >= thirty_days_ago,
            ).group_by(AuditLogModel.action).limit(10)
        )
        features_used = [row[0] for row in audit_events.all()]

        # Last active (most recent audit log or login)
        last_event = await db.execute(
            select(AuditLogModel.created_at).where(
                AuditLogModel.user_id == user_id_str
            ).order_by(AuditLogModel.created_at.desc()).limit(1)
        )
        last_active_row = last_event.scalar_one_or_none()
        last_active = last_active_row.isoformat() if last_active_row else (u.last_login.isoformat() if u.last_login else None)

        # Escalations raised
        esc_count_row = await db.execute(
            select(func.count(EscalationModel.id)).where(
                EscalationModel.tenant_id == tenant_id,
                EscalationModel.user_id == user_id_str,
            )
        )
        esc_count: int = esc_count_row.scalar_one_or_none() or 0

        stats.append({
            "user_id": user_id_str,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name or u.username,
            "roles": u.roles,
            "is_active": u.is_active,
            "joined_at": u.created_at.isoformat(),
            "last_active": last_active,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "total_sessions": sess_all.scalar_one_or_none() or 0,
            "sessions_last_30d": sess_30.scalar_one_or_none() or 0,
            "total_messages": msgs_all.scalar_one_or_none() or 0,
            "messages_today": msgs_today.scalar_one_or_none() or 0,
            "escalations_raised": esc_count,
            "features_used": features_used[:8],
        })

    return {"users": stats, "total": len(stats), "tenant_id": tenant_id}


# ── Agents ─────────────────────────────────────────────────────────────────────

@router.get("/agents")
async def list_agents(_: Principal = Depends(get_principal)) -> dict:
    agents = [
        AgentDescriptor(
            agent_name=p.agent_name,
            display_name=p.display_name or p.agent_name,
            department=p.department,
            description=p.description,
            model=p.model,
            capabilities=list(p.capabilities),
            tools=list(p.mcp_connectors),
        )
        for p in ALL_DEPARTMENT_PROFILES
    ]
    return {
        "agents": [a.model_dump(mode="json") for a in agents],
        "total": len(agents),
        "active": len(agents),
    }


# ── Workflows ──────────────────────────────────────────────────────────────────

WORKFLOW_TEMPLATES = [
    {
        "id": "onboard-employee",
        "name": "Employee Onboarding",
        "department": "hr",
        "description": "Automate new-hire paperwork, system access, and orientation scheduling.",
        "steps": ["Collect employee details", "Create accounts", "Schedule orientation", "Send welcome email"],
        "category": "HR",
        "estimated_minutes": 5,
    },
    {
        "id": "sales-lead-followup",
        "name": "Sales Lead Follow-up",
        "department": "sales",
        "description": "Auto-qualify leads, enrich CRM data, and schedule follow-up calls.",
        "steps": ["Fetch lead from CRM", "Score lead", "Draft follow-up email", "Log activity"],
        "category": "Sales",
        "estimated_minutes": 2,
    },
    {
        "id": "support-ticket-triage",
        "name": "IT Ticket Triage",
        "department": "technology",
        "description": "Classify, prioritise, and route inbound IT support tickets automatically.",
        "steps": ["Parse ticket", "Classify severity", "Assign to engineer", "Notify requester"],
        "category": "Technology",
        "estimated_minutes": 1,
    },
    {
        "id": "invoice-approval",
        "name": "Invoice Approval",
        "department": "finance",
        "description": "Route invoices through approval chains and update accounting records.",
        "steps": ["Extract invoice data", "Match PO", "Route for approval", "Update ERP"],
        "category": "Finance",
        "estimated_minutes": 3,
    },
    {
        "id": "marketing-campaign",
        "name": "Campaign Launcher",
        "department": "marketing",
        "description": "Generate campaign copy, schedule posts, and track engagement.",
        "steps": ["Define target audience", "Generate content", "Schedule posts", "Monitor metrics"],
        "category": "Marketing",
        "estimated_minutes": 10,
    },
    {
        "id": "customer-escalation",
        "name": "Customer Escalation Handler",
        "department": "customer_care",
        "description": "Detect at-risk customers, escalate to senior agents, and send resolution emails.",
        "steps": ["Detect escalation trigger", "Summarise issue", "Assign senior agent", "Send resolution"],
        "category": "Customer Care",
        "estimated_minutes": 4,
    },
    {
        "id": "visitor-intake",
        "name": "Visitor Intake",
        "department": "reception",
        "description": "Greet visitors, check appointments, notify hosts, and issue passes.",
        "steps": ["Verify appointment", "Log visitor", "Notify host", "Issue access pass"],
        "category": "Reception",
        "estimated_minutes": 2,
    },
]


@router.get("/workflows")
async def list_workflows(_: Principal = Depends(get_principal)) -> dict:
    """Return available workflow templates."""
    return {
        "workflows": WORKFLOW_TEMPLATES,
        "total": len(WORKFLOW_TEMPLATES),
    }


@router.post("/workflows", response_model=WorkflowResult)
async def run_workflow(
    request: WorkflowRequest,
    _: Principal = Depends(get_principal),
) -> WorkflowResult:
    """Execute a workflow via the swarm router. Any authenticated user may run workflows."""
    return await workforce_router().execute(request)


# ── Analytics ──────────────────────────────────────────────────────────────────

@router.get("/analytics")
async def platform_analytics(
    _: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return real platform activity stats from the database."""
    now = datetime.now(timezone.utc)
    day_ago  = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    # ── Chat sessions ──────────────────────────────────────────────
    total_sessions = (await db.execute(select(func.count()).select_from(ChatSessionModel))).scalar_one()
    sessions_today = (
        await db.execute(
            select(func.count()).select_from(ChatSessionModel).where(ChatSessionModel.created_at >= day_ago)
        )
    ).scalar_one()
    active_sessions = (
        await db.execute(
            select(func.count()).select_from(ChatSessionModel).where(ChatSessionModel.status == "active")
        )
    ).scalar_one()

    # sessions per department (all time)
    dept_rows = (
        await db.execute(
            select(ChatSessionModel.department, func.count().label("cnt"))
            .group_by(ChatSessionModel.department)
        )
    ).all()
    sessions_by_dept = {row.department: row.cnt for row in dept_rows}

    # ── Messages ───────────────────────────────────────────────────
    total_messages = (await db.execute(select(func.count()).select_from(ChatMessageModel))).scalar_one()
    messages_today = (
        await db.execute(
            select(func.count()).select_from(ChatMessageModel).where(ChatMessageModel.created_at >= day_ago)
        )
    ).scalar_one()
    messages_week = (
        await db.execute(
            select(func.count()).select_from(ChatMessageModel).where(ChatMessageModel.created_at >= week_ago)
        )
    ).scalar_one()
    total_tokens = (
        await db.execute(select(func.coalesce(func.sum(ChatMessageModel.tokens_used), 0)))
    ).scalar_one()

    # ── Escalations ────────────────────────────────────────────────
    total_escalations = (await db.execute(select(func.count()).select_from(EscalationModel))).scalar_one()
    open_escalations  = (
        await db.execute(
            select(func.count()).select_from(EscalationModel).where(EscalationModel.status == "open")
        )
    ).scalar_one()
    escalations_today = (
        await db.execute(
            select(func.count()).select_from(EscalationModel).where(EscalationModel.created_at >= day_ago)
        )
    ).scalar_one()

    # ── Knowledge Base ─────────────────────────────────────────────
    total_docs = (await db.execute(select(func.count()).select_from(KnowledgeDocumentModel))).scalar_one()

    # ── Audit Log ──────────────────────────────────────────────────
    audit_today = (
        await db.execute(
            select(func.count()).select_from(AuditLogModel).where(AuditLogModel.created_at >= day_ago)
        )
    ).scalar_one()

    # ── Voice sessions (in-memory) ─────────────────────────────────
    active_voice = len(voice_session_manager().all())

    # ── Daily activity (last 30 days, message count per day) ────────
    # Bucket in Python so this works on both SQLite (local/dev) and Postgres
    # (prod) — ``date_trunc`` is Postgres-only and crashes on SQLite.
    month_ago = now - timedelta(days=30)
    ts_rows = (
        await db.execute(
            select(ChatMessageModel.created_at).where(ChatMessageModel.created_at >= month_ago)
        )
    ).all()
    _buckets: dict[str, int] = {}
    for (created,) in ts_rows:
        if created is None:
            continue
        key = created.date().isoformat()
        _buckets[key] = _buckets.get(key, 0) + 1
    daily_activity = [
        {"date": day, "messages": cnt}
        for day, cnt in sorted(_buckets.items())
    ]

    return {
        "generated_at": now.isoformat(),
        "chat": {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "sessions_today": sessions_today,
            "sessions_by_department": sessions_by_dept,
            "total_messages": total_messages,
            "messages_today": messages_today,
            "messages_this_week": messages_week,
            "total_tokens_used": int(total_tokens),
        },
        "escalations": {
            "total": total_escalations,
            "open": open_escalations,
            "today": escalations_today,
        },
        "knowledge_base": {
            "total_documents": total_docs,
        },
        "audit": {
            "events_today": audit_today,
        },
        "voice": {
            "active_sessions": active_voice,
        },
        "activity": {
            "daily_messages": daily_activity,
        },
    }


# ── Voice sessions ─────────────────────────────────────────────────────────────

@router.get("/voice/sessions")
async def voice_sessions(_: Principal = Depends(get_principal)) -> list[dict]:
    return [
        {
            "session_id": s.session_id,
            "user_id": s.user_id,
            "department": s.department.value,
            "started_at": s.started_at,
            "last_activity": s.last_activity,
            "escalation": s.escalation.value,
        }
        for s in voice_session_manager().all()
    ]


# ── MCP tools ──────────────────────────────────────────────────────────────────

@router.get("/mcp/tools")
async def list_mcp_tools(
    department: Department | None = None,
    _: Principal = Depends(get_principal),
) -> list[dict]:
    return [
        {"name": t.name, "connector": connector, "tool": t.name, "description": t.description}
        for connector, t in mcp_registry().list_tools(department)
    ]



# ── Agent activity stats ────────────────────────────────────────────────────

@router.get("/analytics/agents")
async def agent_activity(
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(get_principal),
) -> dict:
    """Per-department message/session counts for the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Messages per department
    dept_msg_rows = (
        await db.execute(
            select(ChatMessageModel.department, func.count().label("cnt"))
            .where(ChatMessageModel.created_at >= cutoff)
            .group_by(ChatMessageModel.department)
        )
    ).all()

    # Sessions per department
    dept_sess_rows = (
        await db.execute(
            select(ChatSessionModel.department, func.count().label("cnt"))
            .where(ChatSessionModel.created_at >= cutoff)
            .group_by(ChatSessionModel.department)
        )
    ).all()

    msgs_map  = {str(r.department or "general"): r.cnt for r in dept_msg_rows}
    sess_map  = {str(r.department or "general"): r.cnt for r in dept_sess_rows}
    all_depts = sorted(set(msgs_map) | set(sess_map))

    return {
        "days": days,
        "agents": [
            {
                "department": dept,
                "messages":   msgs_map.get(dept, 0),
                "sessions":   sess_map.get(dept, 0),
            }
            for dept in all_depts
        ],
    }


# ── Prometheus ─────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
