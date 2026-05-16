"""
DevOps / IT MCP server (mock Jira / PagerDuty / GitHub Actions / Kubernetes).
Implements MCP JSON-RPC 2.0 at /mcp/devops.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mcp/devops", tags=["mcp-devops"])

# ── In-memory store ──────────────────────────────────────────────────────────

_tickets: dict[str, dict] = {
    "TICK-001": {"id": "TICK-001", "title": "API latency spike on /chat endpoint",   "priority": "High",   "status": "Open",       "assignee": "Diana Prince",  "type": "Incident",  "created": "2025-05-14"},
    "TICK-002": {"id": "TICK-002", "title": "Upgrade PostgreSQL from 15 to 16",       "priority": "Medium", "status": "In Progress", "assignee": "Liam Nguyen",   "type": "Task",      "created": "2025-05-12"},
    "TICK-003": {"id": "TICK-003", "title": "Voice gateway memory leak",              "priority": "High",   "status": "Open",       "assignee": "Unassigned",    "type": "Bug",       "created": "2025-05-15"},
    "TICK-004": {"id": "TICK-004", "title": "Set up Kubernetes HPA for API pods",     "priority": "Low",    "status": "Done",       "assignee": "Diana Prince",  "type": "Task",      "created": "2025-05-10"},
}

_deployments: dict[str, dict] = {
    "dep-001": {"id": "dep-001", "service": "ai-workforce-api",     "version": "v3.4.1", "environment": "production",  "status": "Healthy", "pods": 3, "last_deploy": "2025-05-15T10:30:00Z"},
    "dep-002": {"id": "dep-002", "service": "ai-workforce-frontend","version": "v2.1.0", "environment": "production",  "status": "Healthy", "pods": 2, "last_deploy": "2025-05-14T16:00:00Z"},
    "dep-003": {"id": "dep-003", "service": "voice-gateway",        "version": "v1.0.8", "environment": "production",  "status": "Warning", "pods": 2, "last_deploy": "2025-05-13T09:00:00Z"},
    "dep-004": {"id": "dep-004", "service": "ai-workforce-api",     "version": "v3.4.2", "environment": "staging",     "status": "Healthy", "pods": 1, "last_deploy": "2025-05-15T14:00:00Z"},
}

_TOOLS = [
    {"name": "devops_list_tickets",      "description": "List IT/DevOps tickets, optionally filtered by status, priority, or type.",   "inputSchema": {"type": "object", "properties": {"status": {"type": "string"}, "priority": {"type": "string"}, "type": {"type": "string"}}}},
    {"name": "devops_get_ticket",        "description": "Get full details of a ticket by ID.",                                         "inputSchema": {"type": "object", "required": ["ticket_id"], "properties": {"ticket_id": {"type": "string"}}}},
    {"name": "devops_create_ticket",     "description": "Create a new incident, task, or bug ticket.",                                 "inputSchema": {"type": "object", "required": ["title", "type"], "properties": {"title": {"type": "string"}, "type": {"type": "string"}, "priority": {"type": "string"}, "description": {"type": "string"}, "assignee": {"type": "string"}}}},
    {"name": "devops_update_ticket",     "description": "Update ticket status, priority, or assignee.",                               "inputSchema": {"type": "object", "required": ["ticket_id"], "properties": {"ticket_id": {"type": "string"}, "status": {"type": "string"}, "priority": {"type": "string"}, "assignee": {"type": "string"}}}},
    {"name": "devops_list_deployments",  "description": "List active deployments, optionally filtered by environment or service.",     "inputSchema": {"type": "object", "properties": {"environment": {"type": "string"}, "service": {"type": "string"}}}},
    {"name": "devops_system_health",     "description": "Return overall system health: deployment statuses and open incidents.",       "inputSchema": {"type": "object", "properties": {}}},
    {"name": "devops_trigger_deploy",    "description": "Simulate triggering a deployment pipeline for a service.",                   "inputSchema": {"type": "object", "required": ["service", "version", "environment"], "properties": {"service": {"type": "string"}, "version": {"type": "string"}, "environment": {"type": "string"}}}},
]


def _list_tickets(args: dict) -> Any:
    tix = list(_tickets.values())
    if s := args.get("status"):
        tix = [t for t in tix if t["status"].lower() == s.lower()]
    if p := args.get("priority"):
        tix = [t for t in tix if t["priority"].lower() == p.lower()]
    if tp := args.get("type"):
        tix = [t for t in tix if t["type"].lower() == tp.lower()]
    return {"tickets": tix, "total": len(tix)}


def _get_ticket(args: dict) -> Any:
    tid = args.get("ticket_id", "")
    return _tickets.get(tid) or {"error": f"Ticket {tid!r} not found"}


def _create_ticket(args: dict) -> Any:
    tid = f"TICK-{str(len(_tickets) + 1).zfill(3)}"
    ticket = {
        "id": tid, "title": args["title"], "type": args["type"],
        "priority": args.get("priority", "Medium"), "status": "Open",
        "assignee": args.get("assignee", "Unassigned"),
        "description": args.get("description", ""),
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    _tickets[tid] = ticket
    return {"created": True, "ticket": ticket}


def _update_ticket(args: dict) -> Any:
    tid = args.get("ticket_id", "")
    if tid not in _tickets:
        return {"error": f"Ticket {tid!r} not found"}
    for k in ("status", "priority", "assignee"):
        if k in args:
            _tickets[tid][k] = args[k]
    return {"updated": True, "ticket": _tickets[tid]}


def _list_deployments(args: dict) -> Any:
    deps = list(_deployments.values())
    if env := args.get("environment"):
        deps = [d for d in deps if d["environment"] == env]
    if svc := args.get("service"):
        deps = [d for d in deps if svc.lower() in d["service"].lower()]
    return {"deployments": deps, "total": len(deps)}


def _system_health(_args: dict) -> Any:
    statuses = [d["status"] for d in _deployments.values()]
    open_incidents = [t for t in _tickets.values() if t["status"] == "Open" and t["type"] == "Incident"]
    overall = "Healthy" if all(s == "Healthy" for s in statuses) else "Degraded"
    return {
        "overall_status":      overall,
        "total_deployments":   len(_deployments),
        "healthy_deployments": statuses.count("Healthy"),
        "warning_deployments": statuses.count("Warning"),
        "open_incidents":      len(open_incidents),
        "open_tickets":        sum(1 for t in _tickets.values() if t["status"] == "Open"),
    }


def _trigger_deploy(args: dict) -> Any:
    dep_id = f"dep-{uuid.uuid4().hex[:6]}"
    dep = {
        "id": dep_id,
        "service":     args["service"],
        "version":     args["version"],
        "environment": args["environment"],
        "status":      "Deploying",
        "pods":        1,
        "last_deploy": datetime.now(timezone.utc).isoformat(),
    }
    _deployments[dep_id] = dep
    return {"triggered": True, "deployment": dep, "message": f"Deployment pipeline started for {args['service']} {args['version']} → {args['environment']}"}


_IMPL = {
    "devops_list_tickets":     _list_tickets,
    "devops_get_ticket":       _get_ticket,
    "devops_create_ticket":    _create_ticket,
    "devops_update_ticket":    _update_ticket,
    "devops_list_deployments": _list_deployments,
    "devops_system_health":    _system_health,
    "devops_trigger_deploy":   _trigger_deploy,
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
        name = req.params.get("name")
        args = req.params.get("arguments", {})
        impl = _IMPL.get(name)
        if not impl:
            return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32601, "message": f"Unknown tool: {name!r}"}}
        try:
            result = impl(args)
            return {"jsonrpc": "2.0", "id": req.id, "result": {"content": [{"type": "text", "text": str(result)}], "isError": False}}
        except Exception as exc:  # noqa: BLE001
            return {"jsonrpc": "2.0", "id": req.id, "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True}}
    return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32601, "message": f"Method not found: {req.method!r}"}}


@router.get("/status")
async def status_rest() -> dict:
    return {"tickets": list(_tickets.values()), "deployments": list(_deployments.values())}
