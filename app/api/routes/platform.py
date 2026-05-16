"""Workflow / agent / health admin endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.agents.profiles import ALL_DEPARTMENT_PROFILES
from app.core.types import Department
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


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


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


@router.post("/workflows", response_model=WorkflowResult)
async def run_workflow(
    request: WorkflowRequest,
    _: Principal = Depends(require_roles("agent")),
) -> WorkflowResult:
    return await workforce_router().execute(request)


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


@router.get("/mcp/tools")
async def list_mcp_tools(
    department: Department | None = None,
    _: Principal = Depends(get_principal),
) -> list[dict]:
    return [
        {"connector": connector, "tool": t.name, "description": t.description}
        for connector, t in mcp_registry().list_tools(department)
    ]


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
