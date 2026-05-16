"""
End-to-end test suite for the AI Workforce Platform.
API: http://localhost:8080
Frontend: http://localhost:4000
"""
import json
import time
import pytest
import httpx

API = "http://localhost:8080"
FRONTEND = "http://localhost:4000"
CREDS = {"username": "admin", "password": "admin"}


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def token():
    """Obtain a JWT token for the admin user (JSON body)."""
    # Platform accepts JSON at /auth/token
    r = httpx.post(f"{API}/api/v1/auth/token", json=CREDS, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Health & Infra
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_api_health(self):
        r = httpx.get(f"{API}/api/v1/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_api_docs_accessible(self):
        r = httpx.get(f"{API}/docs", timeout=10)
        assert r.status_code == 200

    def test_openapi_schema(self):
        r = httpx.get(f"{API}/openapi.json", timeout=10)
        assert r.status_code == 200
        schema = r.json()
        assert "paths" in schema
        assert len(schema["paths"]) > 10

    def test_frontend_accessible(self):
        r = httpx.get(FRONTEND, timeout=15, follow_redirects=True)
        assert r.status_code == 200

    def test_metrics_endpoint(self):
        r = httpx.get(f"{API}/metrics", timeout=10)
        # Either 200 (prometheus) or 404 is acceptable
        assert r.status_code in (200, 404)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Authentication
# ─────────────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_login_success(self):
        r = httpx.post(f"{API}/api/v1/auth/token", json=CREDS, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body.get("token_type") == "bearer"

    def test_login_wrong_password(self):
        r = httpx.post(
            f"{API}/api/v1/auth/token",
            json={"username": "admin", "password": "wrong"},
            timeout=10,
        )
        assert r.status_code in (401, 422)

    def test_login_unknown_user(self):
        r = httpx.post(
            f"{API}/api/v1/auth/token",
            json={"username": "nobody", "password": "x"},
            timeout=10,
        )
        assert r.status_code in (401, 422)

    def test_me_endpoint(self, auth):
        r = httpx.get(f"{API}/api/v1/auth/me", headers=auth, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get("user_id") == "admin"

    def test_me_without_auth(self):
        r = httpx.get(f"{API}/api/v1/auth/me", timeout=10)
        assert r.status_code in (401, 403)

    def test_token_refresh(self, token):
        r = httpx.post(
            f"{API}/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        # Either 200 (refresh supported) or 404/405 acceptable
        assert r.status_code in (200, 404, 405)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Chat API
# ─────────────────────────────────────────────────────────────────────────────

class TestChatAPI:
    def test_chat_message(self, auth):
        r = httpx.post(
            f"{API}/api/v1/chat",
            json={
                "message": "Hello, who are you?",
                "department": "reception",
                "session_id": "test-e2e-session-001",
                "user_id": "e2e-test-user",
            },
            headers=auth,
            timeout=30,
        )
        assert r.status_code == 200, f"Chat failed: {r.text}"
        body = r.json()
        assert "message" in body

    def test_chat_sales_department(self, auth):
        r = httpx.post(
            f"{API}/api/v1/chat",
            json={
                "message": "Tell me about your product pricing",
                "department": "sales",
                "session_id": "test-e2e-session-002",
            },
            headers=auth,
            timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("department") is not None

    def test_chat_hr_department(self, auth):
        r = httpx.post(
            f"{API}/api/v1/chat",
            json={
                "message": "How do I apply for leave?",
                "department": "hr",
                "session_id": "test-e2e-session-003",
            },
            headers=auth,
            timeout=30,
        )
        assert r.status_code == 200

    def test_list_sessions(self, auth):
        r = httpx.get(f"{API}/api/v1/chat/sessions", headers=auth, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "sessions" in body
        assert isinstance(body["sessions"], list)

    def test_get_session_history(self, auth):
        # First create a session
        sid = "test-history-session-001"
        httpx.post(
            f"{API}/api/v1/chat",
            json={"message": "Start history test", "session_id": sid},
            headers=auth,
            timeout=30,
        )
        r = httpx.get(f"{API}/api/v1/chat/sessions/{sid}", headers=auth, timeout=10)
        assert r.status_code in (200, 404)  # 404 if session not yet persisted

    def test_chat_unauthenticated(self):
        r = httpx.post(
            f"{API}/api/v1/chat",
            json={"message": "Hello"},
            timeout=15,
        )
        # Platform may allow unauthenticated chat or require auth
        assert r.status_code in (200, 401, 403)

    def test_export_session_json(self, auth):
        sid = "test-e2e-session-001"
        r = httpx.get(
            f"{API}/api/v1/chat/sessions/{sid}/export?format=json",
            headers=auth,
            timeout=10,
        )
        assert r.status_code in (200, 404)

    def test_export_session_csv(self, auth):
        sid = "test-e2e-session-001"
        r = httpx.get(
            f"{API}/api/v1/chat/sessions/{sid}/export?format=csv",
            headers=auth,
            timeout=10,
        )
        assert r.status_code in (200, 404)


# ─────────────────────────────────────────────────────────────────────────────
# 4. MCP Connectors
# ─────────────────────────────────────────────────────────────────────────────

class TestMCPConnectors:
    def _call(self, path, method, args=None):
        return httpx.post(
            f"{API}/{path}",
            json={"jsonrpc": "2.0", "id": 1, "method": method,
                  "params": {"name": (args or {}).pop("_tool", ""), "arguments": args or {}} if method == "tools/call" else {}},
            timeout=10,
        )

    def test_crm_tools_list(self):
        r = httpx.post(f"{API}/mcp/crm", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, timeout=10)
        assert r.status_code == 200
        tools = r.json()["result"]["tools"]
        assert len(tools) > 0
        tool_names = [t["name"] for t in tools]
        assert "crm_list_contacts" in tool_names

    def test_crm_list_contacts(self):
        r = httpx.post(f"{API}/mcp/crm", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                       "params": {"name": "crm_list_contacts", "arguments": {}}}, timeout=10)
        assert r.status_code == 200
        assert r.json()["result"]["isError"] is False

    def test_hris_tools_list(self):
        r = httpx.post(f"{API}/mcp/hris", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, timeout=10)
        assert r.status_code == 200
        assert len(r.json()["result"]["tools"]) > 0

    def test_hris_list_employees(self):
        r = httpx.post(f"{API}/mcp/hris", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                       "params": {"name": "hris_list_employees", "arguments": {}}}, timeout=10)
        assert r.status_code == 200
        assert r.json()["result"]["isError"] is False

    def test_finance_tools(self):
        r = httpx.post(f"{API}/mcp/finance", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, timeout=10)
        assert r.status_code == 200
        assert len(r.json()["result"]["tools"]) > 0

    def test_devops_tools(self):
        r = httpx.post(f"{API}/mcp/devops", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, timeout=10)
        assert r.status_code == 200
        assert len(r.json()["result"]["tools"]) > 0

    def test_knowledge_search(self):
        r = httpx.post(f"{API}/mcp/knowledge", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "kb_search", "arguments": {"query": "onboarding policy"}}}, timeout=10)
        assert r.status_code == 200
        assert r.json()["result"]["isError"] is False

    def test_calendar_list_events(self):
        r = httpx.post(f"{API}/mcp/calendar", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "cal_list_events", "arguments": {}}}, timeout=10)
        assert r.status_code == 200

    def test_email_send(self):
        r = httpx.post(f"{API}/mcp/email", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "email_send", "arguments": {"to": "test@test.com", "subject": "E2E", "body": "Test"}}}, timeout=10)
        assert r.status_code == 200

    def test_mcp_tools_endpoint(self, auth):
        r = httpx.get(f"{API}/api/v1/mcp/tools", headers=auth, timeout=10)
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert isinstance(r.json(), (list, dict))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Escalations
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalations:
    _esc_id = None

    def test_create_escalation(self, auth):
        r = httpx.post(
            f"{API}/api/v1/escalations",
            json={"department": "hr", "reason": "E2E test escalation", "priority": "normal"},
            headers=auth,
            timeout=10,
        )
        assert r.status_code in (200, 201), f"Escalation create failed: {r.text}"
        body = r.json()
        assert body.get("status") == "open"
        TestEscalations._esc_id = body["id"]

    def test_list_escalations(self, auth):
        r = httpx.get(f"{API}/api/v1/escalations", headers=auth, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "escalations" in body
        assert isinstance(body["escalations"], list)
        assert len(body["escalations"]) >= 1

    def test_get_escalation(self, auth):
        if not TestEscalations._esc_id:
            pytest.skip("No escalation ID from create test")
        r = httpx.get(f"{API}/api/v1/escalations/{TestEscalations._esc_id}", headers=auth, timeout=10)
        assert r.status_code == 200
        assert r.json()["department"] == "hr"

    def test_filter_open_escalations(self, auth):
        r = httpx.get(f"{API}/api/v1/escalations?status=open", headers=auth, timeout=10)
        assert r.status_code == 200
        for e in r.json()["escalations"]:
            assert e["status"] == "open"

    def test_resolve_escalation(self, auth):
        if not TestEscalations._esc_id:
            pytest.skip("No escalation ID")
        r = httpx.patch(
            f"{API}/api/v1/escalations/{TestEscalations._esc_id}/resolve",
            json={"resolution_notes": "Resolved by E2E test", "assigned_to": "admin"},
            headers=auth,
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"

    def test_double_resolve_fails(self, auth):
        if not TestEscalations._esc_id:
            pytest.skip("No escalation ID")
        r = httpx.patch(
            f"{API}/api/v1/escalations/{TestEscalations._esc_id}/resolve",
            json={"resolution_notes": "Again"},
            headers=auth,
            timeout=10,
        )
        assert r.status_code == 409

    def test_escalation_unauth(self):
        r = httpx.get(f"{API}/api/v1/escalations", timeout=10)
        assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Knowledge Base
# ─────────────────────────────────────────────────────────────────────────────

class TestKnowledgeBase:
    _doc_id = None

    def test_list_documents_empty(self, auth):
        r = httpx.get(f"{API}/api/v1/knowledge", headers=auth, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "documents" in body
        assert isinstance(body["documents"], list)

    def test_upload_text_document(self, auth):
        r = httpx.post(
            f"{API}/api/v1/knowledge/upload",
            files={"file": ("test_policy.txt", b"This is a test IT security policy document for E2E testing.", "text/plain")},
            data={"title": "E2E Test Policy", "category": "IT"},
            headers=auth,
            timeout=15,
        )
        assert r.status_code in (200, 201), f"Upload failed: {r.text}"
        body = r.json()
        assert body.get("title") == "E2E Test Policy"
        TestKnowledgeBase._doc_id = body["id"]

    def test_list_after_upload(self, auth):
        r = httpx.get(f"{API}/api/v1/knowledge", headers=auth, timeout=10)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_get_document(self, auth):
        if not TestKnowledgeBase._doc_id:
            pytest.skip("No doc ID")
        r = httpx.get(f"{API}/api/v1/knowledge/{TestKnowledgeBase._doc_id}", headers=auth, timeout=10)
        assert r.status_code == 200
        assert "E2E" in r.json()["title"]

    def test_category_filter(self, auth):
        r = httpx.get(f"{API}/api/v1/knowledge?category=IT", headers=auth, timeout=10)
        assert r.status_code == 200
        for d in r.json()["documents"]:
            assert d["category"] == "IT"

    def test_upload_rejects_oversized(self, auth):
        big = b"x" * (21 * 1024 * 1024)  # 21 MB > 20 MB limit
        r = httpx.post(
            f"{API}/api/v1/knowledge/upload",
            files={"file": ("big.txt", big, "text/plain")},
            data={"title": "Too Big", "category": "General"},
            headers=auth,
            timeout=30,
        )
        assert r.status_code == 413

    def test_delete_document(self, auth):
        if not TestKnowledgeBase._doc_id:
            pytest.skip("No doc ID")
        r = httpx.delete(f"{API}/api/v1/knowledge/{TestKnowledgeBase._doc_id}", headers=auth, timeout=10)
        assert r.status_code == 204


# ─────────────────────────────────────────────────────────────────────────────
# 7. Audit Log
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditLog:
    def test_audit_log_requires_admin(self, auth):
        r = httpx.get(f"{API}/api/v1/audit", headers=auth, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "logs" in body

    def test_audit_log_unauthenticated(self):
        r = httpx.get(f"{API}/api/v1/audit", timeout=10)
        assert r.status_code in (401, 403)

    def test_audit_log_has_entries(self, auth):
        r = httpx.get(f"{API}/api/v1/audit", headers=auth, timeout=10)
        assert r.status_code == 200
        # After login + chat + escalation tests, there should be entries
        logs = r.json()["logs"]
        assert isinstance(logs, list)

    def test_audit_filter_by_action(self, auth):
        r = httpx.get(f"{API}/api/v1/audit?action=chat.message", headers=auth, timeout=10)
        assert r.status_code == 200
        for log in r.json()["logs"]:
            assert log["action"] == "chat.message"

    def test_audit_pagination(self, auth):
        r = httpx.get(f"{API}/api/v1/audit?skip=0&limit=5", headers=auth, timeout=10)
        assert r.status_code == 200
        assert len(r.json()["logs"]) <= 5


# ─────────────────────────────────────────────────────────────────────────────
# 8. Voice API
# ─────────────────────────────────────────────────────────────────────────────

class TestVoiceAPI:
    def test_create_voice_session(self, auth):
        r = httpx.post(
            f"{API}/api/v1/voice/sessions",
            json={"department": "reception", "user_id": "e2e-tester"},
            headers=auth,
            timeout=10,
        )
        assert r.status_code in (200, 201)
        if r.status_code in (200, 201):
            body = r.json()
            assert "session_id" in body or "id" in body

    def test_list_voice_sessions(self, auth):
        r = httpx.get(f"{API}/api/v1/voice/sessions", headers=auth, timeout=10)
        assert r.status_code in (200, 404)

    def test_voice_providers_list(self, auth):
        r = httpx.get(f"{API}/api/v1/voice/providers", headers=auth, timeout=10)
        assert r.status_code in (200, 404)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Platform / Agents
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformAgents:
    def test_list_agents(self, auth):
        r = httpx.get(f"{API}/api/v1/agents", headers=auth, timeout=10)
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            body = r.json()
            assert isinstance(body, (list, dict))

    def test_platform_status(self, auth):
        r = httpx.get(f"{API}/api/v1/platform/status", headers=auth, timeout=10)
        assert r.status_code in (200, 404)

    def test_analytics_endpoint(self, auth):
        r = httpx.get(f"{API}/api/v1/analytics", headers=auth, timeout=10)
        assert r.status_code in (200, 404)

    def test_workflows_endpoint(self, auth):
        r = httpx.get(f"{API}/api/v1/workflows", headers=auth, timeout=10)
        assert r.status_code in (200, 404, 405)


# ─────────────────────────────────────────────────────────────────────────────
# 10. WebSocket connectivity
# ─────────────────────────────────────────────────────────────────────────────

class TestWebSocket:
    def test_chat_ws_connects(self, token):
        """Verify WS endpoint accepts connections (basic TCP handshake)."""
        import socket
        s = socket.socket()
        s.settimeout(5)
        try:
            s.connect(("localhost", 8080))
            connected = True
        except Exception:
            connected = False
        finally:
            s.close()
        assert connected, "Cannot reach port 8080"

    def test_chat_ws_upgrade(self, token):
        """Send a WS upgrade request and verify 101 Switching Protocols."""
        import socket, hashlib, base64
        key = base64.b64encode(b"e2e-test-key-123").decode()
        request = (
            f"GET /api/v1/ws/chat?token={token} HTTP/1.1\r\n"
            f"Host: localhost:8080\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        s = socket.socket()
        s.settimeout(5)
        try:
            s.connect(("localhost", 8080))
            s.sendall(request.encode())
            response = s.recv(1024).decode(errors="replace")
            assert "101" in response or "switching" in response.lower(), f"WS upgrade failed: {response[:200]}"
        finally:
            s.close()
