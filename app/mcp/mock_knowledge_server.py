"""Knowledge-base MCP server (mock RAG / document search).

Backed by an in-memory document store; replace with ChromaDB or
Pinecone when KNOWLEDGE_INDEX_URL is set.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mcp/knowledge", tags=["mcp-knowledge"])

_docs: dict[str, dict] = {
    "doc-001": {"id": "doc-001", "title": "Enterprise Onboarding Guide",    "category": "HR",      "content": "Step-by-step onboarding process for new employees including IT setup, badge access, and benefits enrollment.", "updated": "2025-04-01"},
    "doc-002": {"id": "doc-002", "title": "IT Security Policy",             "category": "IT",      "content": "Password requirements, VPN usage, device encryption, and incident reporting procedures.", "updated": "2025-03-15"},
    "doc-003": {"id": "doc-003", "title": "Sales Playbook Q2 2025",         "category": "Sales",   "content": "Objection handling scripts, pricing tiers, and competitive differentiation for the Q2 campaign.", "updated": "2025-05-01"},
    "doc-004": {"id": "doc-004", "title": "Finance Expense Policy",         "category": "Finance", "content": "Per-diem rates, approval limits, reimbursement timelines, and disallowed expense categories.", "updated": "2025-01-10"},
    "doc-005": {"id": "doc-005", "title": "Customer Support Runbook",       "category": "Support", "content": "Escalation matrix, SLA commitments, refund workflow, and common resolution templates.", "updated": "2025-05-10"},
}

_TOOLS = [
    {"name": "kb_search",          "description": "Semantic search across the knowledge base. Returns top-N matching documents.", "inputSchema": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "category": {"type": "string"}, "limit": {"type": "integer", "default": 5}}}},
    {"name": "kb_get_document",    "description": "Retrieve a specific document by ID.",                                          "inputSchema": {"type": "object", "required": ["doc_id"], "properties": {"doc_id": {"type": "string"}}}},
    {"name": "kb_add_document",    "description": "Add a new document to the knowledge base.",                                    "inputSchema": {"type": "object", "required": ["title", "content", "category"], "properties": {"title": {"type": "string"}, "content": {"type": "string"}, "category": {"type": "string"}}}},
    {"name": "kb_list_categories", "description": "List all document categories and counts.",                                     "inputSchema": {"type": "object", "properties": {}}},
]


def _kb_search(args: dict) -> Any:
    query = args.get("query", "").lower()
    cat   = (args.get("category") or "").lower()
    limit = int(args.get("limit", 5))
    results = [
        {**d, "score": sum(w in d["title"].lower() + d["content"].lower() for w in query.split())}
        for d in _docs.values()
        if not cat or cat in d["category"].lower()
    ]
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:limit], "total": len(results)}


def _kb_get(args: dict) -> Any:
    return _docs.get(args.get("doc_id", "")) or {"error": "Document not found"}


def _kb_add(args: dict) -> Any:
    did = f"doc-{uuid.uuid4().hex[:6]}"
    doc = {"id": did, "title": args["title"], "content": args["content"],
           "category": args["category"], "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    _docs[did] = doc
    return {"created": True, "document": doc}


def _kb_categories(_args: dict) -> Any:
    from collections import Counter
    counts = Counter(d["category"] for d in _docs.values())
    return {"categories": dict(counts), "total_documents": len(_docs)}


_IMPL = {"kb_search": _kb_search, "kb_get_document": _kb_get, "kb_add_document": _kb_add, "kb_list_categories": _kb_categories}


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


@router.get("/documents")
async def list_docs_rest() -> dict:
    return {"documents": list(_docs.values())}
