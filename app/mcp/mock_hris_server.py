"""
HRIS MCP server (mock BambooHR / Workday / Gusto).
Implements MCP JSON-RPC 2.0 at /mcp/hris.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mcp/hris", tags=["mcp-hris"])

# ── In-memory store ──────────────────────────────────────────────────────────

_employees: dict[str, dict] = {
    "e001": {"id": "e001", "name": "Diana Prince",  "email": "diana@company.com",  "department": "Engineering",  "role": "Senior Engineer",   "status": "active", "start_date": "2022-03-01", "salary": 95000},
    "e002": {"id": "e002", "name": "James Okonkwo", "email": "james@company.com",  "department": "Marketing",    "role": "Marketing Manager", "status": "active", "start_date": "2021-07-15", "salary": 78000},
    "e003": {"id": "e003", "name": "Sofia Reyes",   "email": "sofia@company.com",  "department": "Finance",      "role": "Finance Analyst",   "status": "active", "start_date": "2023-01-10", "salary": 72000},
    "e004": {"id": "e004", "name": "Liam Nguyen",   "email": "liam@company.com",   "department": "HR",           "role": "HR Specialist",     "status": "active", "start_date": "2020-09-20", "salary": 65000},
}

_leave_requests: dict[str, dict] = {
    "l001": {"id": "l001", "employee_id": "e001", "type": "Annual", "start": "2025-06-01", "end": "2025-06-07", "days": 5, "status": "Approved"},
    "l002": {"id": "l002", "employee_id": "e002", "type": "Sick",   "start": "2025-05-20", "end": "2025-05-21", "days": 2, "status": "Approved"},
}

_TOOLS = [
    {"name": "hris_list_employees",     "description": "List all employees, optionally filtered by department or status.", "inputSchema": {"type": "object", "properties": {"department": {"type": "string"}, "status": {"type": "string"}}}},
    {"name": "hris_get_employee",       "description": "Get full details of an employee by ID.",                           "inputSchema": {"type": "object", "required": ["employee_id"], "properties": {"employee_id": {"type": "string"}}}},
    {"name": "hris_create_employee",    "description": "Onboard a new employee.",                                          "inputSchema": {"type": "object", "required": ["name", "email", "department", "role"], "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "department": {"type": "string"}, "role": {"type": "string"}, "salary": {"type": "number"}}}},
    {"name": "hris_update_employee",    "description": "Update employee record (role, department, salary, status).",       "inputSchema": {"type": "object", "required": ["employee_id"], "properties": {"employee_id": {"type": "string"}, "role": {"type": "string"}, "department": {"type": "string"}, "salary": {"type": "number"}, "status": {"type": "string"}}}},
    {"name": "hris_request_leave",      "description": "Submit a leave request for an employee.",                          "inputSchema": {"type": "object", "required": ["employee_id", "type", "start", "end"], "properties": {"employee_id": {"type": "string"}, "type": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}}}},
    {"name": "hris_list_leave_requests","description": "List leave requests, optionally for a specific employee.",         "inputSchema": {"type": "object", "properties": {"employee_id": {"type": "string"}, "status": {"type": "string"}}}},
    {"name": "hris_headcount_summary",  "description": "Return headcount breakdown by department.",                        "inputSchema": {"type": "object", "properties": {}}},
]


def _list_employees(args: dict) -> Any:
    emps = list(_employees.values())
    if d := args.get("department"):
        emps = [e for e in emps if d.lower() in e["department"].lower()]
    if s := args.get("status"):
        emps = [e for e in emps if e["status"] == s]
    return {"employees": emps, "total": len(emps)}


def _get_employee(args: dict) -> Any:
    eid = args.get("employee_id", "")
    return _employees.get(eid) or {"error": f"Employee {eid!r} not found"}


def _create_employee(args: dict) -> Any:
    eid = f"e{uuid.uuid4().hex[:6]}"
    emp = {"id": eid, "name": args["name"], "email": args["email"],
           "department": args["department"], "role": args["role"],
           "status": "active", "salary": args.get("salary", 0),
           "start_date": date.today().isoformat()}
    _employees[eid] = emp
    return {"created": True, "employee": emp}


def _update_employee(args: dict) -> Any:
    eid = args.get("employee_id", "")
    if eid not in _employees:
        return {"error": f"Employee {eid!r} not found"}
    for k in ("role", "department", "salary", "status"):
        if k in args:
            _employees[eid][k] = args[k]
    return {"updated": True, "employee": _employees[eid]}


def _request_leave(args: dict) -> Any:
    lid = f"l{uuid.uuid4().hex[:6]}"
    start = datetime.fromisoformat(args["start"])
    end   = datetime.fromisoformat(args["end"])
    days  = max(1, (end - start).days + 1)
    req   = {"id": lid, "employee_id": args["employee_id"], "type": args["type"],
             "start": args["start"], "end": args["end"], "days": days, "status": "Pending"}
    _leave_requests[lid] = req
    return {"submitted": True, "leave_request": req}


def _list_leave(args: dict) -> Any:
    reqs = list(_leave_requests.values())
    if eid := args.get("employee_id"):
        reqs = [r for r in reqs if r["employee_id"] == eid]
    if s := args.get("status"):
        reqs = [r for r in reqs if r["status"] == s]
    return {"leave_requests": reqs, "total": len(reqs)}


def _headcount_summary(_args: dict) -> Any:
    from collections import Counter
    counts = Counter(e["department"] for e in _employees.values())
    return {"headcount_by_department": dict(counts), "total_employees": len(_employees)}


_IMPL = {
    "hris_list_employees":     _list_employees,
    "hris_get_employee":       _get_employee,
    "hris_create_employee":    _create_employee,
    "hris_update_employee":    _update_employee,
    "hris_request_leave":      _request_leave,
    "hris_list_leave_requests": _list_leave,
    "hris_headcount_summary":  _headcount_summary,
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


@router.get("/employees")
async def list_employees_rest() -> dict:
    return {"employees": list(_employees.values()), "leave_requests": list(_leave_requests.values())}
