"""
Analytics MCP server — platform usage metrics.
Implements MCP JSON-RPC 2.0 at /mcp/analytics.

Tools exposed
─────────────
  analytics_get_summary            – overall platform metrics (today vs all-time)
  analytics_get_department_breakdown – message / session counts per department
  analytics_get_agent_activity      – per-agent message / escalation counts
  analytics_get_trend               – daily message volume for last N days
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mcp/analytics", tags=["mcp-analytics"])

# ── Tool schema ───────────────────────────────────────────────────────────────

_TOOLS = [
    {
        "name": "analytics_get_summary",
        "description": "Return high-level platform metrics: total messages, active sessions, escalations, and registered users.",
        "inputSchema": {"type": "object", "properties": {"tenant_id": {"type": "string"}}},
    },
    {
        "name": "analytics_get_department_breakdown",
        "description": "Return message and session counts grouped by department/agent type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "period_days": {"type": "integer", "description": "Look-back window in days (default 30)."},
            },
        },
    },
    {
        "name": "analytics_get_agent_activity",
        "description": "Return per-agent message counts and escalation rates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "department": {"type": "string", "description": "Filter to a single department (optional)."},
            },
        },
    },
    {
        "name": "analytics_get_trend",
        "description": "Return daily message volumes for the last N days.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},
                "days": {"type": "integer", "description": "Number of days to look back (default 7, max 90)."},
            },
        },
    },
]

# ── DB-backed implementations ─────────────────────────────────────────────────


async def _analytics_get_summary(args: dict) -> Any:
    """Overall platform metrics from the database."""
    from app.db.session import AsyncSessionLocal
    from app.db.models import (
        ChatMessageModel,
        ChatSessionModel,
        EscalationModel,
        UserModel,
    )
    from sqlalchemy import func, select

    tenant_id: str = args.get("tenant_id", "default")
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as db:
        total_msgs = (
            await db.execute(
                select(func.count(ChatMessageModel.id)).where(
                    ChatMessageModel.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none() or 0

        msgs_today = (
            await db.execute(
                select(func.count(ChatMessageModel.id)).where(
                    ChatMessageModel.tenant_id == tenant_id,
                    ChatMessageModel.created_at >= today_start,
                )
            )
        ).scalar_one_or_none() or 0

        total_sessions = (
            await db.execute(
                select(func.count(ChatSessionModel.id)).where(
                    ChatSessionModel.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none() or 0

        active_sessions = (
            await db.execute(
                select(func.count(ChatSessionModel.id)).where(
                    ChatSessionModel.tenant_id == tenant_id,
                    ChatSessionModel.updated_at >= today_start,
                )
            )
        ).scalar_one_or_none() or 0

        total_escalations = (
            await db.execute(
                select(func.count(EscalationModel.id)).where(
                    EscalationModel.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none() or 0

        open_escalations = (
            await db.execute(
                select(func.count(EscalationModel.id)).where(
                    EscalationModel.tenant_id == tenant_id,
                    EscalationModel.status == "open",
                )
            )
        ).scalar_one_or_none() or 0

        total_users = (
            await db.execute(
                select(func.count(UserModel.id)).where(
                    UserModel.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none() or 0

    return {
        "tenant_id": tenant_id,
        "as_of": now.isoformat(),
        "messages": {"total": total_msgs, "today": msgs_today},
        "sessions": {"total": total_sessions, "active_today": active_sessions},
        "escalations": {"total": total_escalations, "open": open_escalations},
        "users": {"total": total_users},
    }


async def _analytics_get_department_breakdown(args: dict) -> Any:
    from app.db.session import AsyncSessionLocal
    from app.db.models import ChatMessageModel, ChatSessionModel
    from sqlalchemy import func, select

    tenant_id: str = args.get("tenant_id", "default")
    period_days: int = min(int(args.get("period_days", 30)), 365)
    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    async with AsyncSessionLocal() as db:
        # Messages per department
        msg_rows = (
            await db.execute(
                select(
                    ChatMessageModel.department,
                    func.count(ChatMessageModel.id).label("count"),
                ).where(
                    ChatMessageModel.tenant_id == tenant_id,
                    ChatMessageModel.created_at >= since,
                    ChatMessageModel.role == "assistant",
                ).group_by(ChatMessageModel.department)
            )
        ).fetchall()

        # Sessions per department
        sess_rows = (
            await db.execute(
                select(
                    ChatSessionModel.department,
                    func.count(ChatSessionModel.id).label("count"),
                ).where(
                    ChatSessionModel.tenant_id == tenant_id,
                    ChatSessionModel.updated_at >= since,
                ).group_by(ChatSessionModel.department)
            )
        ).fetchall()

    msg_by_dept = {r.department or "unknown": r.count for r in msg_rows}
    sess_by_dept = {r.department or "unknown": r.count for r in sess_rows}
    all_depts = sorted(set(msg_by_dept) | set(sess_by_dept))

    breakdown = [
        {
            "department": dept,
            "messages": msg_by_dept.get(dept, 0),
            "sessions": sess_by_dept.get(dept, 0),
        }
        for dept in all_depts
    ]
    return {"period_days": period_days, "breakdown": breakdown}


async def _analytics_get_agent_activity(args: dict) -> Any:
    from app.db.session import AsyncSessionLocal
    from app.db.models import ChatMessageModel, EscalationModel
    from sqlalchemy import func, select

    tenant_id: str = args.get("tenant_id", "default")
    dept_filter: str | None = args.get("department")

    async with AsyncSessionLocal() as db:
        q = (
            select(
                ChatMessageModel.department,
                func.count(ChatMessageModel.id).label("msg_count"),
            )
            .where(
                ChatMessageModel.tenant_id == tenant_id,
                ChatMessageModel.role == "assistant",
            )
            .group_by(ChatMessageModel.department)
        )
        if dept_filter:
            q = q.where(ChatMessageModel.department == dept_filter)
        msg_rows = (await db.execute(q)).fetchall()

        esc_rows = (
            await db.execute(
                select(
                    EscalationModel.department,
                    func.count(EscalationModel.id).label("esc_count"),
                ).where(
                    EscalationModel.tenant_id == tenant_id
                ).group_by(EscalationModel.department)
            )
        ).fetchall()

    esc_by_dept = {r.department or "unknown": r.esc_count for r in esc_rows}

    activity = []
    for r in msg_rows:
        dept = r.department or "unknown"
        msgs = r.msg_count
        escs = esc_by_dept.get(dept, 0)
        activity.append({
            "department": dept,
            "messages_handled": msgs,
            "escalations": escs,
            "escalation_rate_pct": round(escs / msgs * 100, 1) if msgs else 0,
        })

    return {"agent_activity": sorted(activity, key=lambda x: x["messages_handled"], reverse=True)}


async def _analytics_get_trend(args: dict) -> Any:
    from app.db.session import AsyncSessionLocal
    from app.db.models import ChatMessageModel
    from sqlalchemy import func, select, cast
    from sqlalchemy import Date as SADate

    tenant_id: str = args.get("tenant_id", "default")
    days: int = min(int(args.get("days", 7)), 90)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(
                    cast(ChatMessageModel.created_at, SADate).label("day"),
                    func.count(ChatMessageModel.id).label("count"),
                ).where(
                    ChatMessageModel.tenant_id == tenant_id,
                    ChatMessageModel.created_at >= since,
                ).group_by("day").order_by("day")
            )
        ).fetchall()

    trend = [{"date": str(r.day), "messages": r.count} for r in rows]
    return {"days": days, "trend": trend}


# ── Dispatch table ────────────────────────────────────────────────────────────

_IMPL: dict[str, Any] = {
    "analytics_get_summary":              _analytics_get_summary,
    "analytics_get_department_breakdown": _analytics_get_department_breakdown,
    "analytics_get_agent_activity":       _analytics_get_agent_activity,
    "analytics_get_trend":                _analytics_get_trend,
}


class RPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = None
    method: str
    params: dict = {}


@router.post("")
async def mcp_handler(req: RPCRequest) -> dict:
    if req.method == "tools/list":
        return {"jsonrpc": "2.0", "id": req.id, "result": {"tools": _TOOLS}}

    if req.method == "tools/call":
        name = req.params.get("name", "")
        args = req.params.get("arguments", {})
        impl = _IMPL.get(name)
        if not impl:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32601, "message": f"Unknown tool: {name!r}"},
            }
        try:
            result = await impl(args)
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "result": {"content": [{"type": "text", "text": str(result)}], "isError": False},
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True},
            }

    return {
        "jsonrpc": "2.0",
        "id": req.id,
        "error": {"code": -32601, "message": f"Method not found: {req.method!r}"},
    }


@router.get("/summary")
async def analytics_summary_rest() -> dict:
    """REST convenience endpoint — returns the same data as analytics_get_summary."""
    return await _analytics_get_summary({"tenant_id": "default"})
