"""Calendar MCP server (mock Google Calendar / Outlook / Calendly)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mcp/calendar", tags=["mcp-calendar"])

_now = datetime.now(timezone.utc)

_events: dict[str, dict] = {
    "evt-001": {"id": "evt-001", "title": "Sales Kickoff Q2",        "attendees": ["alice@company.com", "bob@company.com"], "start": "2025-05-20T09:00:00Z", "end": "2025-05-20T10:00:00Z", "type": "meeting", "status": "confirmed"},
    "evt-002": {"id": "evt-002", "title": "Product Demo — Acme Corp", "attendees": ["carol@company.com"],                   "start": "2025-05-21T14:00:00Z", "end": "2025-05-21T15:00:00Z", "type": "demo",    "status": "confirmed"},
    "evt-003": {"id": "evt-003", "title": "Board Meeting",            "attendees": ["ceo@company.com", "cfo@company.com"],  "start": "2025-05-22T10:00:00Z", "end": "2025-05-22T12:00:00Z", "type": "meeting", "status": "confirmed"},
}

_TOOLS = [
    {"name": "cal_list_events",   "description": "List upcoming calendar events.", "inputSchema": {"type": "object", "properties": {"days_ahead": {"type": "integer", "default": 7}, "attendee": {"type": "string"}}}},
    {"name": "cal_get_event",     "description": "Get a specific event by ID.",    "inputSchema": {"type": "object", "required": ["event_id"], "properties": {"event_id": {"type": "string"}}}},
    {"name": "cal_create_event",  "description": "Schedule a new event.",          "inputSchema": {"type": "object", "required": ["title", "start", "end"], "properties": {"title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "attendees": {"type": "array", "items": {"type": "string"}}, "type": {"type": "string"}}}},
    {"name": "cal_cancel_event",  "description": "Cancel/delete an event.",        "inputSchema": {"type": "object", "required": ["event_id"], "properties": {"event_id": {"type": "string"}}}},
    {"name": "cal_find_free_slot","description": "Find next available time slot.", "inputSchema": {"type": "object", "properties": {"duration_minutes": {"type": "integer", "default": 60}, "attendees": {"type": "array", "items": {"type": "string"}}}}},
]


def _list_events(args: dict) -> Any:
    evts = list(_events.values())
    if a := args.get("attendee"):
        evts = [e for e in evts if any(a.lower() in att.lower() for att in e["attendees"])]
    return {"events": evts, "total": len(evts)}

def _get_event(args: dict) -> Any:
    return _events.get(args.get("event_id", "")) or {"error": "Event not found"}

def _create_event(args: dict) -> Any:
    eid = f"evt-{uuid.uuid4().hex[:6]}"
    evt = {"id": eid, "title": args["title"], "start": args["start"], "end": args["end"],
           "attendees": args.get("attendees", []), "type": args.get("type", "meeting"), "status": "confirmed"}
    _events[eid] = evt
    return {"created": True, "event": evt}

def _cancel_event(args: dict) -> Any:
    eid = args.get("event_id", "")
    if eid not in _events:
        return {"error": f"Event {eid!r} not found"}
    _events[eid]["status"] = "cancelled"
    return {"cancelled": True, "event_id": eid}

def _find_slot(args: dict) -> Any:
    dur = int(args.get("duration_minutes", 60))
    slot_start = _now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    slot_end   = slot_start + timedelta(minutes=dur)
    return {"free_slot": {"start": slot_start.isoformat(), "end": slot_end.isoformat(), "duration_minutes": dur}}


_IMPL = {"cal_list_events": _list_events, "cal_get_event": _get_event, "cal_create_event": _create_event, "cal_cancel_event": _cancel_event, "cal_find_free_slot": _find_slot}


class RPCRequest(BaseModel):
    jsonrpc: str = "2.0"; id: Any = None; method: str; params: dict = {}


@router.post("")
async def mcp_handler(req: RPCRequest) -> dict:
    if req.method == "tools/list":
        return {"jsonrpc": "2.0", "id": req.id, "result": {"tools": _TOOLS}}
    if req.method == "tools/call":
        name = req.params.get("name"); args = req.params.get("arguments", {})
        impl = _IMPL.get(name)
        if not impl:
            return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32601, "message": f"Unknown tool: {name!r}"}}
        try:
            return {"jsonrpc": "2.0", "id": req.id, "result": {"content": [{"type": "text", "text": str(impl(args))}], "isError": False}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": req.id, "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True}}
    return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32601, "message": f"Method not found: {req.method!r}"}}
