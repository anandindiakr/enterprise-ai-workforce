"""Email / marketing MCP server (mock SendGrid / Mailchimp / Resend)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mcp/email", tags=["mcp-email"])

_sent: list[dict] = []
_campaigns: dict[str, dict] = {
    "cmp-001": {"id": "cmp-001", "name": "Q2 Product Launch",       "status": "sent",    "recipients": 4820, "opens": 1930, "clicks": 412, "sent_at": "2025-05-10"},
    "cmp-002": {"id": "cmp-002", "name": "Enterprise Nurture Track", "status": "active",  "recipients": 1240, "opens": 0,    "clicks": 0,   "sent_at": None},
    "cmp-003": {"id": "cmp-003", "name": "Customer Success Check-in","status": "draft",   "recipients": 0,    "opens": 0,    "clicks": 0,   "sent_at": None},
}

_TOOLS = [
    {"name": "email_send",            "description": "Send a transactional email to one or more recipients.", "inputSchema": {"type": "object", "required": ["to", "subject", "body"], "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "cc": {"type": "string"}, "template": {"type": "string"}}}},
    {"name": "email_list_campaigns",  "description": "List all email campaigns.",                             "inputSchema": {"type": "object", "properties": {"status": {"type": "string"}}}},
    {"name": "email_campaign_stats",  "description": "Get open/click stats for a campaign.",                  "inputSchema": {"type": "object", "required": ["campaign_id"], "properties": {"campaign_id": {"type": "string"}}}},
    {"name": "email_create_campaign", "description": "Create a new email campaign.",                          "inputSchema": {"type": "object", "required": ["name", "subject", "body"], "properties": {"name": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "recipients": {"type": "integer"}}}},
    {"name": "email_get_sent_log",    "description": "Return the last N transactional emails sent.",          "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}}},
]


def _send_email(args: dict) -> Any:
    record = {"id": uuid.uuid4().hex[:8], "to": args["to"], "subject": args["subject"],
              "sent_at": datetime.now(timezone.utc).isoformat(), "status": "delivered"}
    _sent.append(record)
    return {"sent": True, "message_id": record["id"], "to": args["to"]}

def _list_campaigns(args: dict) -> Any:
    camps = list(_campaigns.values())
    if s := args.get("status"):
        camps = [c for c in camps if c["status"] == s]
    return {"campaigns": camps, "total": len(camps)}

def _campaign_stats(args: dict) -> Any:
    c = _campaigns.get(args.get("campaign_id", ""))
    if not c:
        return {"error": "Campaign not found"}
    total = c["recipients"] or 1
    return {**c, "open_rate": round(c["opens"] / total * 100, 1), "click_rate": round(c["clicks"] / total * 100, 1)}

def _create_campaign(args: dict) -> Any:
    cid = f"cmp-{uuid.uuid4().hex[:6]}"
    camp = {"id": cid, "name": args["name"], "status": "draft", "recipients": args.get("recipients", 0),
            "opens": 0, "clicks": 0, "sent_at": None}
    _campaigns[cid] = camp
    return {"created": True, "campaign": camp}

def _sent_log(args: dict) -> Any:
    limit = int(args.get("limit", 20))
    return {"sent_emails": _sent[-limit:], "total_sent": len(_sent)}


_IMPL = {"email_send": _send_email, "email_list_campaigns": _list_campaigns, "email_campaign_stats": _campaign_stats, "email_create_campaign": _create_campaign, "email_get_sent_log": _sent_log}


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
