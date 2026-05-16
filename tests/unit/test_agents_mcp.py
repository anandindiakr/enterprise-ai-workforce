"""Unit tests for agent utilities and MCP mock servers."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# MCP mock server — CRM
# ---------------------------------------------------------------------------

class TestCRMMCP:
    def _client(self):
        from fastapi import FastAPI
        from app.mcp.mock_crm_server import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_tools_list(self):
        c = self._client()
        resp = c.post("/mcp/crm", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        assert resp.status_code == 200
        tools = resp.json()["result"]["tools"]
        assert len(tools) > 0

    def test_list_contacts(self):
        c = self._client()
        resp = c.post(
            "/mcp/crm",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "crm_list_contacts", "arguments": {}}},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["isError"] is False

    def test_unknown_tool(self):
        c = self._client()
        resp = c.post(
            "/mcp/crm",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "nonexistent_tool", "arguments": {}}},
        )
        assert resp.status_code == 200
        assert "error" in resp.json()


# ---------------------------------------------------------------------------
# MCP mock server — Knowledge base
# ---------------------------------------------------------------------------

class TestKnowledgeMCP:
    def _client(self):
        from fastapi import FastAPI
        from app.mcp.mock_knowledge_server import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_kb_search(self):
        c = self._client()
        resp = c.post(
            "/mcp/knowledge",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "kb_search", "arguments": {"query": "onboarding"}}},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["isError"] is False

    def test_list_categories(self):
        c = self._client()
        resp = c.post(
            "/mcp/knowledge",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "kb_list_categories", "arguments": {}}},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["isError"] is False
        assert "categories" in result["content"][0]["text"]

    def test_add_document(self):
        c = self._client()
        resp = c.post(
            "/mcp/knowledge",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "kb_add_document",
                             "arguments": {"title": "Test Doc", "content": "Hello", "category": "Test"}}},
        )
        assert resp.status_code == 200
        assert "created" in resp.json()["result"]["content"][0]["text"]


# ---------------------------------------------------------------------------
# MCP mock server — Calendar
# ---------------------------------------------------------------------------

class TestCalendarMCP:
    def _client(self):
        from fastapi import FastAPI
        from app.mcp.mock_calendar_server import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_list_events(self):
        c = self._client()
        resp = c.post(
            "/mcp/calendar",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "cal_list_events", "arguments": {}}},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["isError"] is False

    def test_create_event(self):
        c = self._client()
        resp = c.post(
            "/mcp/calendar",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "cal_create_event",
                             "arguments": {"title": "Demo", "start": "2025-06-01T10:00:00Z", "end": "2025-06-01T11:00:00Z"}}},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["isError"] is False


# ---------------------------------------------------------------------------
# MCP mock server — Email
# ---------------------------------------------------------------------------

class TestEmailMCP:
    def _client(self):
        from fastapi import FastAPI
        from app.mcp.mock_email_server import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_send_email(self):
        c = self._client()
        resp = c.post(
            "/mcp/email",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "email_send",
                             "arguments": {"to": "test@acme.com", "subject": "Hi", "body": "Hello!"}}},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["isError"] is False

    def test_list_campaigns(self):
        c = self._client()
        resp = c.post(
            "/mcp/email",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "email_list_campaigns", "arguments": {}}},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert "campaigns" in result["content"][0]["text"]


# ---------------------------------------------------------------------------
# Text extraction helper
# ---------------------------------------------------------------------------

class TestTextExtraction:
    def test_plain_text(self):
        from app.api.routes.knowledge import _extract_text
        content = _extract_text(b"Hello world", "test.txt", "text/plain")
        assert "Hello world" in content

    def test_json_extraction(self):
        from app.api.routes.knowledge import _extract_text
        content = _extract_text(b'{"key": "value"}', "data.json", "application/json")
        assert "value" in content

    def test_empty_bytes(self):
        from app.api.routes.knowledge import _extract_text
        content = _extract_text(b"", "empty.txt", "text/plain")
        assert content == ""
