"""
Finance / ERP MCP server (mock NetSuite / SAP / QuickBooks).
Implements MCP JSON-RPC 2.0 at /mcp/finance.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mcp/finance", tags=["mcp-finance"])

# ── In-memory store ──────────────────────────────────────────────────────────

_invoices: dict[str, dict] = {
    "INV-001": {"id": "INV-001", "vendor": "AWS Cloud Services",     "amount": 12400.00, "currency": "USD", "due_date": "2025-06-01", "status": "Pending",   "category": "Infrastructure"},
    "INV-002": {"id": "INV-002", "vendor": "Office Supplies Co",     "amount":   850.50, "currency": "USD", "due_date": "2025-05-25", "status": "Approved",  "category": "Operations"},
    "INV-003": {"id": "INV-003", "vendor": "Salesforce Inc",         "amount":  5200.00, "currency": "USD", "due_date": "2025-06-15", "status": "Pending",   "category": "Software"},
    "INV-004": {"id": "INV-004", "vendor": "Legal & Compliance LLP", "amount":  3100.00, "currency": "USD", "due_date": "2025-05-20", "status": "Paid",      "category": "Legal"},
}

_budgets: dict[str, dict] = {
    "Engineering":  {"department": "Engineering",  "allocated": 150000, "spent": 87000,  "remaining": 63000, "period": "Q2-2025"},
    "Marketing":    {"department": "Marketing",    "allocated":  80000, "spent": 54000,  "remaining": 26000, "period": "Q2-2025"},
    "HR":           {"department": "HR",           "allocated":  40000, "spent": 18500,  "remaining": 21500, "period": "Q2-2025"},
    "Technology":   {"department": "Technology",   "allocated": 120000, "spent": 99500,  "remaining": 20500, "period": "Q2-2025"},
    "Finance":      {"department": "Finance",      "allocated":  35000, "spent": 22000,  "remaining": 13000, "period": "Q2-2025"},
    "Sales":        {"department": "Sales",        "allocated":  90000, "spent": 61000,  "remaining": 29000, "period": "Q2-2025"},
}

_TOOLS = [
    {"name": "finance_list_invoices",   "description": "List invoices, optionally filtered by status or category.",  "inputSchema": {"type": "object", "properties": {"status": {"type": "string"}, "category": {"type": "string"}}}},
    {"name": "finance_get_invoice",     "description": "Get a specific invoice by ID.",                              "inputSchema": {"type": "object", "required": ["invoice_id"], "properties": {"invoice_id": {"type": "string"}}}},
    {"name": "finance_create_invoice",  "description": "Create a new invoice or expense record.",                   "inputSchema": {"type": "object", "required": ["vendor", "amount"], "properties": {"vendor": {"type": "string"}, "amount": {"type": "number"}, "currency": {"type": "string"}, "due_date": {"type": "string"}, "category": {"type": "string"}}}},
    {"name": "finance_approve_invoice", "description": "Approve or reject an invoice.",                             "inputSchema": {"type": "object", "required": ["invoice_id", "action"], "properties": {"invoice_id": {"type": "string"}, "action": {"type": "string", "enum": ["approve", "reject"]}}}},
    {"name": "finance_list_budgets",    "description": "List department budgets for the current period.",            "inputSchema": {"type": "object", "properties": {"department": {"type": "string"}}}},
    {"name": "finance_budget_summary",  "description": "Return overall financial health: total spend vs budget.",   "inputSchema": {"type": "object", "properties": {}}},
    {"name": "finance_expense_report",  "description": "Generate an expense report grouped by category.",           "inputSchema": {"type": "object", "properties": {"period": {"type": "string"}}}},
]


def _list_invoices(args: dict) -> Any:
    invs = list(_invoices.values())
    if s := args.get("status"):
        invs = [i for i in invs if i["status"].lower() == s.lower()]
    if c := args.get("category"):
        invs = [i for i in invs if i["category"].lower() == c.lower()]
    return {"invoices": invs, "total": len(invs), "total_amount": sum(i["amount"] for i in invs)}


def _get_invoice(args: dict) -> Any:
    iid = args.get("invoice_id", "")
    return _invoices.get(iid) or {"error": f"Invoice {iid!r} not found"}


def _create_invoice(args: dict) -> Any:
    iid = f"INV-{str(len(_invoices) + 1).zfill(3)}"
    inv = {
        "id": iid, "vendor": args["vendor"], "amount": args["amount"],
        "currency": args.get("currency", "USD"),
        "due_date": args.get("due_date", ""),
        "status": "Pending", "category": args.get("category", "General"),
    }
    _invoices[iid] = inv
    return {"created": True, "invoice": inv}


def _approve_invoice(args: dict) -> Any:
    iid    = args.get("invoice_id", "")
    action = args.get("action", "approve")
    if iid not in _invoices:
        return {"error": f"Invoice {iid!r} not found"}
    _invoices[iid]["status"] = "Approved" if action == "approve" else "Rejected"
    return {"updated": True, "invoice": _invoices[iid]}


def _list_budgets(args: dict) -> Any:
    buds = list(_budgets.values())
    if d := args.get("department"):
        buds = [b for b in buds if d.lower() in b["department"].lower()]
    return {"budgets": buds}


def _budget_summary(_args: dict) -> Any:
    total_alloc = sum(b["allocated"] for b in _budgets.values())
    total_spent = sum(b["spent"]     for b in _budgets.values())
    return {
        "total_allocated": total_alloc,
        "total_spent":     total_spent,
        "total_remaining": total_alloc - total_spent,
        "utilisation_pct": round(total_spent / total_alloc * 100, 1) if total_alloc else 0,
        "period": "Q2-2025",
    }


def _expense_report(args: dict) -> Any:
    from collections import defaultdict
    by_cat: dict[str, float] = defaultdict(float)
    for inv in _invoices.values():
        if inv["status"] != "Rejected":
            by_cat[inv["category"]] += inv["amount"]
    return {"expense_by_category": dict(by_cat), "period": args.get("period", "Q2-2025"), "total": sum(by_cat.values())}


_IMPL = {
    "finance_list_invoices":   _list_invoices,
    "finance_get_invoice":     _get_invoice,
    "finance_create_invoice":  _create_invoice,
    "finance_approve_invoice": _approve_invoice,
    "finance_list_budgets":    _list_budgets,
    "finance_budget_summary":  _budget_summary,
    "finance_expense_report":  _expense_report,
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


@router.get("/invoices")
async def list_invoices_rest() -> dict:
    return {"invoices": list(_invoices.values()), "budgets": list(_budgets.values())}
