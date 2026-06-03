"""Workflow / agent / health / analytics admin endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
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
from app.swarms.router import workforce_router
from app.telemetry.metrics import REGISTRY
from app.voice.session import voice_session_manager

router = APIRouter(tags=["platform"])


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ── Agents ─────────────────────────────────────────────────────────────────────

@router.get("/agents")
async def list_agents(_: Principal = Depends(get_principal)) -> dict:
    agents = [
        AgentDescriptor(
            agent_name=p.agent_name,
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
    _: Principal = Depends(require_roles("agent")),
) -> WorkflowResult:
    """Execute a workflow via the swarm router."""
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

    # ── Daily activity (last 7 days, message count per day) ────────
    daily_rows = (
        await db.execute(
            select(
                func.date_trunc("day", ChatMessageModel.created_at).label("day"),
                func.count().label("cnt"),
            )
            .where(ChatMessageModel.created_at >= week_ago)
            .group_by("day")
            .order_by("day")
        )
    ).all()
    daily_activity = [
        {"date": str(row.day.date()) if row.day else "", "messages": row.cnt}
        for row in daily_rows
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


# ── Prometheus ─────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
