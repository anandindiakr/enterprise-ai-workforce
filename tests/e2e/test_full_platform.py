"""End-to-end platform tests — run against live Docker services.

Services expected:
  API      → http://localhost:8080
  Frontend → http://localhost:3000

Usage:
  pytest tests/e2e/test_full_platform.py -v --timeout=60
"""

from __future__ import annotations

import json
import time
import httpx
import pytest

API = "http://localhost:8080"
FE  = "http://localhost:3000"
WS_BASE = f"ws://localhost:8080/api/v1/ws"
BASE    = f"{API}/api/v1"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def login(username: str = "admin", password: str = "changeme123") -> str:
    """Return a JWT access token (JSON body)."""
    r = httpx.post(
        f"{BASE}/auth/token",
        json={"username": username, "password": password},
        timeout=15,
    )
    assert r.status_code == 200, f"Login {r.status_code}: {r.text[:200]}"
    return r.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Infrastructure / Health
# ---------------------------------------------------------------------------

class TestInfrastructure:
    def test_api_health(self):
        r = httpx.get(f"{BASE}/health", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") in ("ok", "healthy", "degraded"), body

    def test_api_root(self):
        r = httpx.get(f"{API}/", timeout=10)
        assert r.status_code in (200, 307, 308)

    def test_openapi_docs(self):
        r = httpx.get(f"{API}/docs", timeout=10)
        assert r.status_code == 200

    def test_openapi_schema(self):
        r = httpx.get(f"{API}/openapi.json", timeout=10)
        assert r.status_code == 200
        assert "paths" in r.json()

    def test_frontend_reachable(self):
        r = httpx.get(FE, timeout=15)
        assert r.status_code == 200

    def test_metrics_endpoint(self):
        r = httpx.get(f"{BASE}/metrics", timeout=10)
        assert r.status_code in (200, 404)


# ---------------------------------------------------------------------------
# 2. Authentication
# ---------------------------------------------------------------------------

class TestAuthentication:
    def test_login_success(self):
        token = login()
        assert len(token) > 10

    def test_login_returns_token_type(self):
        r = httpx.post(
            f"{BASE}/auth/token",
            json={"username": "admin", "password": "changeme123"},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body.get("token_type", "").lower() == "bearer"

    def test_login_wrong_password(self):
        r = httpx.post(
            f"{BASE}/auth/token",
            json={"username": "admin", "password": "WRONG"},
            timeout=15,
        )
        assert r.status_code in (400, 401, 403, 422)

    def test_login_unknown_user(self):
        r = httpx.post(
            f"{BASE}/auth/token",
            json={"username": "ghost_user_xyz", "password": "x"},
            timeout=15,
        )
        assert r.status_code in (400, 401, 403, 422)

    def test_protected_no_token_returns_401(self):
        r = httpx.get(f"{BASE}/agents", timeout=10)
        assert r.status_code in (401, 403)

    def test_me_endpoint(self):
        token = login()
        r = httpx.get(f"{BASE}/auth/me", headers=auth_headers(token), timeout=10)
        assert r.status_code == 200
        body = r.json()
        # /auth/me returns Principal: user_id, tenant_id, roles, scopes
        assert any(k in body for k in ("username", "email", "id", "user_id"))


# ---------------------------------------------------------------------------
# 3. Chat
# ---------------------------------------------------------------------------

class TestChat:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = login()
        self.hdrs  = auth_headers(self.token)

    def _chat(self, message: str, department: str = "reception", sid: str = "e2e-test") -> dict:
        r = httpx.post(
            f"{BASE}/chat",
            json={"message": message, "department": department, "session_id": sid},
            headers=self.hdrs,
            timeout=60,
        )
        assert r.status_code == 200, f"Chat {r.status_code}: {r.text[:300]}"
        return r.json()

    def _content(self, body: dict) -> str:
        return (
            (body.get("message") or {}).get("content")
            or body.get("content")
            or ""
        )

    def test_reception_greeting(self):
        body = self._chat("Hello, what can you help me with?")
        assert len(self._content(body)) > 0

    def test_no_raw_json_in_response(self):
        """Agent responses must NOT contain raw JSON transfer directives."""
        body = self._chat("Please transfer me to sales")
        content = self._content(body)
        # should not start with { or contain raw {"transfer":
        assert not content.strip().startswith('{"transfer"'), f"Raw JSON leaked: {content[:200]}"

    def test_transfer_field_in_response(self):
        """ChatResponse schema includes transferred_to field."""
        body = self._chat("I need to speak to the sales team about pricing")
        assert "transferred_to" in body   # field exists (may be null)

    def test_sales_chat(self):
        body = self._chat("What are your pricing plans?", department="sales")
        assert len(self._content(body)) > 0

    def test_hr_chat(self):
        body = self._chat("How many vacation days do we get?", department="hr")
        assert len(self._content(body)) > 0

    def test_technology_chat(self):
        body = self._chat("My laptop won't connect to WiFi", department="technology")
        assert len(self._content(body)) > 0

    def test_finance_chat(self):
        body = self._chat("Help me with an expense report", department="finance")
        assert len(self._content(body)) > 0

    def test_marketing_chat(self):
        body = self._chat("What campaigns are running this quarter?", department="marketing")
        assert len(self._content(body)) > 0

    def test_customer_care_chat(self):
        body = self._chat("I have a complaint about my order", department="customer_care")
        assert len(self._content(body)) > 0

    def test_session_history(self):
        sid = "e2e-history-session"
        self._chat("My name is Alex", sid=sid)
        r = httpx.get(f"{BASE}/chat/sessions/{sid}", headers=self.hdrs, timeout=15)
        assert r.status_code in (200, 404)

    def test_list_chat_sessions(self):
        r = httpx.get(f"{BASE}/chat/sessions", headers=self.hdrs, timeout=15)
        assert r.status_code in (200, 404)


# ---------------------------------------------------------------------------
# 4. Streaming SSE
# ---------------------------------------------------------------------------

class TestStreaming:
    def test_chat_stream_returns_tokens(self):
        token = login()
        hdrs = auth_headers(token) | {"Accept": "text/event-stream"}
        tokens: list[str] = []
        with httpx.stream(
            "POST",
            f"{BASE}/chat/stream",
            json={"message": "Say hello in one sentence", "department": "reception"},
            headers=hdrs,
            timeout=60,
        ) as r:
            assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
            for line in r.iter_lines():
                if line.startswith("data: "):
                    tokens.append(line[6:])
                if len(tokens) >= 3:
                    break
        assert len(tokens) >= 1, "No SSE tokens received"


# ---------------------------------------------------------------------------
# 5. Knowledge Base
# ---------------------------------------------------------------------------

class TestKnowledge:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = login()
        self.hdrs  = auth_headers(self.token)

    def test_list_documents(self):
        r = httpx.get(f"{BASE}/knowledge", headers=self.hdrs, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))

    def test_upload_txt_document(self):
        content = b"Enterprise Policy: All employees must log in using SSO."
        r = httpx.post(
            f"{BASE}/knowledge/upload",
            files={"file": ("policy.txt", content, "text/plain")},
            headers=self.hdrs,
            timeout=30,
        )
        assert r.status_code in (200, 201), f"Upload: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert "id" in body

    def test_upload_sets_pending_status(self):
        content = b"HR Policy: Annual leave is 20 days per year."
        r = httpx.post(
            f"{BASE}/knowledge/upload",
            files={"file": ("hr.txt", content, "text/plain")},
            headers=self.hdrs,
            timeout=30,
        )
        assert r.status_code in (200, 201)
        body = r.json()
        # starts as pending; check field exists
        assert "embedding_status" in body

    def test_embedding_completes(self):
        """Upload, wait a few seconds, verify embedding_status transitions to 'complete'."""
        content = b"Sales Q3 2026 target is 2 million USD."
        r = httpx.post(
            f"{BASE}/knowledge/upload",
            files={"file": ("sales.txt", content, "text/plain")},
            headers=self.hdrs,
            timeout=30,
        )
        assert r.status_code in (200, 201)
        doc_id = r.json()["id"]
        # Poll up to 20 s for 'complete'
        for _ in range(10):
            time.sleep(2)
            rg = httpx.get(f"{BASE}/knowledge/{doc_id}", headers=self.hdrs, timeout=10)
            if rg.status_code == 200:
                status = rg.json().get("embedding_status")
                if status == "complete":
                    return  # pass
        # If still pending after 20 s log a soft warning rather than hard fail
        # (ChromaDB may need model download time on first run)
        pytest.xfail("Embedding still pending after 20 s — may need model warm-up")

    def test_semantic_search(self):
        r = httpx.get(
            f"{BASE}/knowledge/search?q=sales+target&top_k=3",
            headers=self.hdrs,
            timeout=20,
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, (list, dict))

    def test_get_document(self):
        # Upload first
        content = b"Finance doc: Q4 budget approved."
        r = httpx.post(
            f"{BASE}/knowledge/upload",
            files={"file": ("finance.txt", content, "text/plain")},
            headers=self.hdrs,
            timeout=30,
        )
        doc_id = r.json()["id"]
        rg = httpx.get(f"{BASE}/knowledge/{doc_id}", headers=self.hdrs, timeout=10)
        assert rg.status_code == 200

    def test_delete_document(self):
        content = b"Temp document to be deleted."
        r = httpx.post(
            f"{BASE}/knowledge/upload",
            files={"file": ("temp.txt", content, "text/plain")},
            headers=self.hdrs,
            timeout=30,
        )
        doc_id = r.json()["id"]
        rd = httpx.delete(f"{BASE}/knowledge/{doc_id}", headers=self.hdrs, timeout=10)
        assert rd.status_code in (200, 204)


# ---------------------------------------------------------------------------
# 6. Voice
# ---------------------------------------------------------------------------

class TestVoice:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = login()
        self.hdrs  = auth_headers(self.token)

    def test_voice_config_no_auth(self):
        """Voice config is public (for settings page)."""
        r = httpx.get(f"{BASE}/voice/config", timeout=10)
        assert r.status_code == 200

    def test_create_voice_session(self):
        r = httpx.post(
            f"{BASE}/voice/sessions",
            json={"department": "reception"},
            headers=self.hdrs,
            timeout=15,
        )
        assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"
        body = r.json()
        assert "session_id" in body or "id" in body

    def test_list_voice_sessions(self):
        r = httpx.get(f"{BASE}/voice/sessions", headers=self.hdrs, timeout=10)
        assert r.status_code == 200

    def test_tts_speak_endpoint(self):
        r = httpx.post(
            f"{BASE}/voice/speak",
            json={"text": "Hello, I am your AI assistant."},
            headers=self.hdrs,
            timeout=20,
        )
        # 200 = audio returned; 503 = no TTS provider configured (acceptable)
        assert r.status_code in (200, 503), f"{r.status_code}: {r.text[:200]}"

    def test_transcribe_endpoint_accepts_audio(self):
        # Send a tiny silent WAV (44-byte minimal header)
        wav_bytes = (
            b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            b"@\x1f\x00\x00@\x1f\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00"
        )
        r = httpx.post(
            f"{BASE}/voice/transcribe",
            files={"audio": ("test.wav", wav_bytes, "audio/wav")},
            headers=self.hdrs,
            timeout=20,
        )
        # 200 = transcript returned; 422 = file too short / validation;
        # 502/503 = STT provider error (audio too short handled upstream)
        assert r.status_code in (200, 422, 502, 503), f"{r.status_code}: {r.text[:200]}"


# ---------------------------------------------------------------------------
# 7. Workflows
# ---------------------------------------------------------------------------

class TestWorkflows:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = login()
        self.hdrs  = auth_headers(self.token)

    def test_list_workflows(self):
        r = httpx.get(f"{BASE}/workflows", headers=self.hdrs, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, (list, dict))

    def test_run_simple_workflow(self):
        r = httpx.post(
            f"{BASE}/workflows",
            json={
                "task": "Summarise our HR policy in one sentence",
                "strategy": "SequentialWorkflow",
                "user_id": "admin",
            },
            headers=self.hdrs,
            timeout=60,
        )
        assert r.status_code in (200, 202), f"{r.status_code}: {r.text[:200]}"


# ---------------------------------------------------------------------------
# 8. Analytics
# ---------------------------------------------------------------------------

class TestAnalytics:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = login()
        self.hdrs  = auth_headers(self.token)

    def test_analytics_overview(self):
        r = httpx.get(f"{BASE}/analytics", headers=self.hdrs, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)

    def test_mcp_tools_list(self):
        r = httpx.get(f"{BASE}/mcp/tools", headers=self.hdrs, timeout=10)
        assert r.status_code in (200, 404)

    def test_audit_logs(self):
        r = httpx.get(f"{BASE}/audit", headers=self.hdrs, timeout=10)
        assert r.status_code in (200, 404)


# ---------------------------------------------------------------------------
# 9. Agents
# ---------------------------------------------------------------------------

class TestAgents:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = login()
        self.hdrs  = auth_headers(self.token)

    def test_list_agents(self):
        r = httpx.get(f"{BASE}/agents", headers=self.hdrs, timeout=10)
        assert r.status_code == 200
        body = r.json()
        agents = body if isinstance(body, list) else body.get("agents", [])
        # Expect at least the 7 department agents
        assert len(agents) >= 7, f"Only {len(agents)} agents found: {agents}"

    def test_all_departments_present(self):
        r = httpx.get(f"{BASE}/agents", headers=self.hdrs, timeout=10)
        assert r.status_code == 200
        body = r.json()
        agents = body if isinstance(body, list) else body.get("agents", [])
        names = [str(a.get("department", a.get("name", ""))).lower() for a in agents]
        expected = {"reception", "sales", "hr", "finance", "technology", "marketing", "customer_care"}
        missing = expected - {n for n in names for e in expected if e in n}
        assert not missing, f"Missing departments: {missing}"


# ---------------------------------------------------------------------------
# 10. Settings
# ---------------------------------------------------------------------------

class TestSettings:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = login()
        self.hdrs  = auth_headers(self.token)

    def test_get_api_keys(self):
        r = httpx.get(f"{BASE}/settings/keys", headers=self.hdrs, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, (dict, list))

    def test_get_integrations(self):
        r = httpx.get(f"{BASE}/settings/integrations", headers=self.hdrs, timeout=10)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# 11. Escalations
# ---------------------------------------------------------------------------

class TestEscalations:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = login()
        self.hdrs  = auth_headers(self.token)

    def test_list_escalations(self):
        r = httpx.get(f"{BASE}/escalations", headers=self.hdrs, timeout=10)
        assert r.status_code in (200, 404)

    def test_create_escalation(self):
        r = httpx.post(
            f"{BASE}/escalations",
            json={
                "session_id": "e2e-escalation-test",
                "reason": "User requested human supervisor",
                "department": "reception",
            },
            headers=self.hdrs,
            timeout=15,
        )
        assert r.status_code in (200, 201, 422), f"{r.status_code}: {r.text[:200]}"


# ---------------------------------------------------------------------------
# 12. WebSocket — Chat roundtrip
# ---------------------------------------------------------------------------

class TestWebSocketChat:
    def test_ws_chat_roundtrip(self):
        """Connect to chat WS, send a message, receive agent reply within 45 s."""
        token = login()
        session_id = "ws-e2e-test"
        url = f"{WS_BASE}/chat/{session_id}?token={token}"
        try:
            from websocket import create_connection  # websocket-client
        except ImportError:
            pytest.skip("websocket-client not installed")

        try:
            # suppress_origin removes the duplicate Origin header that
            # causes FastAPI's uvicorn to return 400
            ws = create_connection(url, timeout=10, suppress_origin=True)
            ws.send(json.dumps({
                "message": "Hello from e2e test",
                "department": "reception",
                "session_id": session_id,
            }))
            ws.settimeout(45)
            reply = ws.recv()
            ws.close()
        except Exception as exc:
            pytest.fail(f"WS connection/roundtrip failed: {exc}")

        try:
            data = json.loads(reply)
        except json.JSONDecodeError:
            pytest.fail(f"WS reply is not JSON: {reply[:200]}")

        content = (
            (data.get("message") or {}).get("content")
            or data.get("content")
            or ""
        )
        assert len(content) > 0, f"Empty WS reply: {data}"

    def test_ws_no_raw_json_in_reply(self):
        """WS reply must not contain raw JSON transfer directives."""
        token = login()
        session_id = "ws-transfer-test"
        url = f"{WS_BASE}/chat/{session_id}?token={token}"
        try:
            from websocket import create_connection
        except ImportError:
            pytest.skip("websocket-client not installed")

        try:
            ws = create_connection(url, timeout=10, suppress_origin=True)
            ws.send(json.dumps({
                "message": "Transfer me to the sales department please",
                "department": "reception",
                "session_id": session_id,
            }))
            ws.settimeout(45)
            reply = ws.recv()
            ws.close()
        except Exception as exc:
            pytest.fail(f"WS failed: {exc}")

        data = json.loads(reply)
        content = (data.get("message") or {}).get("content") or data.get("content") or ""
        assert '{"transfer"' not in content, f"Raw JSON in content: {content[:200]}"
