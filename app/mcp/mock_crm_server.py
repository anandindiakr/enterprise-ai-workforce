"""
Built-in mock CRM MCP server.

Implements a minimal MCP JSON-RPC 2.0 surface at /mcp/crm so the Sales Agent
can call real tools without needing an external CRM integration.

Endpoints
---------
POST /mcp/crm          JSON-RPC 2.0 handler (tools/list, tools/call)
GET  /mcp/crm/contacts  Quick REST browse (for the dashboard)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mcp/crm", tags=["mcp-crm"])

# ── In-memory CRM store ──────────────────────────────────────────────────────

_contacts: dict[str, dict] = {
    "c001": {
        "id": "c001", "name": "Alice Chen", "email": "alice@example.com",
        "company": "Acme Corp", "stage": "Qualified", "value": 24000,
        "last_contact": "2025-05-10", "notes": "Interested in enterprise plan.",
    },
    "c002": {
        "id": "c002", "name": "Bob Martinez", "email": "bob@acmecorp.com",
        "company": "Global Ltd", "stage": "Proposal", "value": 48000,
        "last_contact": "2025-05-12", "notes": "Demo scheduled for next week.",
    },
    "c003": {
        "id": "c003", "name": "Carol Osei", "email": "carol@techfirm.io",
        "company": "TechFirm", "stage": "Negotiation", "value": 120000,
        "last_contact": "2025-05-14", "notes": "Reviewing contract terms.",
    },
}

_deals: dict[str, dict] = {
    "d001": {"id": "d001", "contact_id": "c001", "title": "Enterprise Seat Expansion", "value": 24000, "stage": "Qualified", "close_date": "2025-06-30"},
    "d002": {"id": "d002", "contact_id": "c002", "title": "Platform License", "value": 48000, "stage": "Proposal", "close_date": "2025-06-15"},
    "d003": {"id": "d003", "contact_id": "c003", "title": "Strategic Partnership", "value": 120000, "stage": "Negotiation", "close_date": "2025-05-30"},
}

# ── MCP tool registry ────────────────────────────────────────────────────────

_TOOLS = [
    {
        "name": "crm_list_contacts",
        "description": "Return a list of CRM contacts, optionally filtered by name or stage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "Optional substring to filter by name/company"},
                "stage": {"type": "string", "description": "Filter by sales stage (Qualified/Proposal/Negotiation/Closed Won/Closed Lost)"},
            },
        },
    },
    {
        "name": "crm_get_contact",
        "description": "Get full details of a single contact by ID.",
        "inputSchema": {
            "type": "object",
            "required": ["contact_id"],
            "properties": {"contact_id": {"type": "string"}},
        },
    },
    {
        "name": "crm_create_contact",
        "description": "Create a new CRM contact.",
        "inputSchema": {
            "type": "object",
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "company": {"type": "string"},
                "stage": {"type": "string"},
                "value": {"type": "number"},
                "notes": {"type": "string"},
            },
        },
    },
    {
        "name": "crm_update_contact",
        "description": "Update an existing contact (partial update). Returns updated contact.",
        "inputSchema": {
            "type": "object",
            "required": ["contact_id"],
            "properties": {
                "contact_id": {"type": "string"},
                "stage": {"type": "string"},
                "notes": {"type": "string"},
                "value": {"type": "number"},
            },
        },
    },
    {
        "name": "crm_list_deals",
        "description": "Return all open deals, optionally filtered by contact_id.",
        "inputSchema": {
            "type": "object",
            "properties": {"contact_id": {"type": "string"}},
        },
    },
    {
        "name": "crm_pipeline_summary",
        "description": "Return a summary of the current sales pipeline (total value by stage).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ── Tool implementations ─────────────────────────────────────────────────────

def _crm_list_contacts(args: dict) -> Any:
    contacts = list(_contacts.values())
    f = (args.get("filter") or "").lower()
    stage = (args.get("stage") or "").lower()
    if f:
        contacts = [c for c in contacts if f in c["name"].lower() or f in c.get("company", "").lower()]
    if stage:
        contacts = [c for c in contacts if c["stage"].lower() == stage]
    return {"contacts": contacts, "total": len(contacts)}


def _crm_get_contact(args: dict) -> Any:
    cid = args.get("contact_id", "")
    if cid not in _contacts:
        return {"error": f"Contact {cid!r} not found"}
    return _contacts[cid]


def _crm_create_contact(args: dict) -> Any:
    cid = f"c{uuid.uuid4().hex[:6]}"
    contact = {
        "id": cid,
        "name": args["name"],
        "email": args["email"],
        "company": args.get("company", ""),
        "stage": args.get("stage", "Lead"),
        "value": args.get("value", 0),
        "notes": args.get("notes", ""),
        "last_contact": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    _contacts[cid] = contact
    return {"created": True, "contact": contact}


def _crm_update_contact(args: dict) -> Any:
    cid = args.get("contact_id", "")
    if cid not in _contacts:
        return {"error": f"Contact {cid!r} not found"}
    for key in ("stage", "notes", "value"):
        if key in args:
            _contacts[cid][key] = args[key]
    _contacts[cid]["last_contact"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {"updated": True, "contact": _contacts[cid]}


def _crm_list_deals(args: dict) -> Any:
    deals = list(_deals.values())
    cid = args.get("contact_id")
    if cid:
        deals = [d for d in deals if d["contact_id"] == cid]
    return {"deals": deals, "total": len(deals)}


def _crm_pipeline_summary(_args: dict) -> Any:
    from collections import defaultdict
    summary: dict[str, int] = defaultdict(int)
    for deal in _deals.values():
        summary[deal["stage"]] += deal["value"]
    total = sum(summary.values())
    return {"pipeline": dict(summary), "total_pipeline_value": total, "open_deals": len(_deals)}


_TOOL_IMPL = {
    "crm_list_contacts":  _crm_list_contacts,
    "crm_get_contact":    _crm_get_contact,
    "crm_create_contact": _crm_create_contact,
    "crm_update_contact": _crm_update_contact,
    "crm_list_deals":     _crm_list_deals,
    "crm_pipeline_summary": _crm_pipeline_summary,
}


# ── JSON-RPC 2.0 handler ─────────────────────────────────────────────────────

class RPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = None
    method: str
    params: dict = {}


def _rpc_error(id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def _rpc_ok(id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


@router.post("")
async def mcp_handler(req: RPCRequest) -> dict:
    if req.method == "tools/list":
        return _rpc_ok(req.id, {"tools": _TOOLS})

    if req.method == "tools/call":
        tool_name = req.params.get("name")
        tool_args = req.params.get("arguments", {})
        impl = _TOOL_IMPL.get(tool_name)
        if not impl:
            return _rpc_error(req.id, -32601, f"Unknown tool: {tool_name!r}")
        try:
            result = impl(tool_args)
            return _rpc_ok(req.id, {"content": [{"type": "text", "text": str(result)}], "isError": False})
        except Exception as exc:  # noqa: BLE001
            return _rpc_ok(req.id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})

    return _rpc_error(req.id, -32601, f"Method not found: {req.method!r}")


# ── Quick REST browse ────────────────────────────────────────────────────────

@router.get("/contacts")
async def list_contacts_rest() -> dict:
    return {"contacts": list(_contacts.values()), "deals": list(_deals.values())}
