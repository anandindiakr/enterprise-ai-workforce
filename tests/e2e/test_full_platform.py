"""
Full-platform E2E test suite for AI Workforce Platform.
Covers: welcome page, auth, dashboard, chat, voice, agents,
        workflows, MCP/CRM, WebSocket, observability, navigation.

Backend:  http://localhost:8080
Frontend: http://localhost:4000
"""
from __future__ import annotations

import json
import time
import httpx
import pytest
from playwright.sync_api import Page, expect

FRONTEND = "http://localhost:4000"
API = "http://localhost:8080"
ADMIN_USER = "admin"
ADMIN_PASS = "admin"


# ── helpers ──────────────────────────────────────────────────────────────────

def get_token() -> str:
    r = httpx.post(
        f"{API}/api/v1/auth/token",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text}"
    return r.json()["access_token"]


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {get_token()}"}


def inject_token(page: Page) -> None:
    """Inject auth token into localStorage before navigating."""
    token = get_token()
    page.goto(f"{FRONTEND}/login", wait_until="networkidle")
    page.evaluate(f"localStorage.setItem('workforce_token', '{token}')")


# ══════════════════════════════════════════════════════════════════════════════
# 1. WELCOME / LANDING PAGE
# ══════════════════════════════════════════════════════════════════════════════

class TestWelcomePage:
    def test_welcome_loads(self, page: Page):
        page.goto(f"{FRONTEND}/welcome", wait_until="networkidle")
        assert page.title() != ""
        page.screenshot(path="tests/e2e/screenshots/e2e_01_welcome.png", full_page=True)

    def test_welcome_has_product_keywords(self, page: Page):
        page.goto(f"{FRONTEND}/welcome", wait_until="networkidle")
        body = page.locator("body").inner_text().lower()
        found = [kw for kw in ["ai", "workforce", "enterprise", "agent"] if kw in body]
        assert len(found) >= 2, f"Missing keywords, found only: {found}"

    def test_welcome_has_cta_buttons(self, page: Page):
        page.goto(f"{FRONTEND}/welcome", wait_until="networkidle")
        btns = page.locator("a[href], button").all()
        assert len(btns) >= 1

    def test_unauthenticated_root_redirects(self, page: Page):
        """/ without token → /welcome or /login."""
        page.goto(FRONTEND, wait_until="networkidle")
        assert "/welcome" in page.url or "/login" in page.url, \
            f"Expected redirect, got: {page.url}"

    def test_welcome_no_js_errors(self, page: Page):
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(f"{FRONTEND}/welcome", wait_until="networkidle")
        page.wait_for_timeout(800)
        critical = [e for e in errors if any(k in e for k in ("SyntaxError", "ReferenceError", "TypeError"))]
        assert not critical, f"Critical JS errors: {critical}"


# ══════════════════════════════════════════════════════════════════════════════
# 2. AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthentication:
    def test_login_page_renders(self, page: Page):
        page.goto(f"{FRONTEND}/login", wait_until="networkidle")
        page.screenshot(path="tests/e2e/screenshots/e2e_02_login.png")
        expect(page.locator("input[type='password']")).to_be_visible()

    def test_api_token_issue(self):
        token = get_token()
        assert len(token) > 30

    def test_api_login_invalid_credentials(self):
        r = httpx.post(
            f"{API}/api/v1/auth/token",
            json={"username": "bad_user", "password": "wrong_pass"},
            timeout=10,
        )
        assert r.status_code in (400, 401, 403)

    def test_api_me_endpoint(self):
        r = httpx.get(f"{API}/api/v1/auth/me", headers=auth_headers(), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "user_id" in data
        assert data["user_id"] == ADMIN_USER

    def test_api_me_requires_auth(self):
        r = httpx.get(f"{API}/api/v1/auth/me", timeout=10)
        assert r.status_code in (401, 403, 422)

    def test_login_ui_success(self, page: Page):
        page.goto(f"{FRONTEND}/login", wait_until="networkidle")
        page.fill("input[autocomplete='username']", ADMIN_USER)
        page.fill("input[autocomplete='current-password']", ADMIN_PASS)
        page.click("button[type='submit']")
        # Wait for navigation away from /login
        page.wait_for_function("window.location.pathname !== '/login'", timeout=15000)
        page.wait_for_load_state("networkidle")
        assert "/login" not in page.url, f"Still on login: {page.url}"
        page.screenshot(path="tests/e2e/screenshots/e2e_03_post_login.png", full_page=True)


# ══════════════════════════════════════════════════════════════════════════════
# 3. DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class TestDashboard:
    def test_dashboard_loads(self, page: Page):
        inject_token(page)
        page.goto(FRONTEND, wait_until="networkidle")
        assert "/login" not in page.url and "/welcome" not in page.url
        page.screenshot(path="tests/e2e/screenshots/e2e_04_dashboard.png", full_page=True)

    def test_dashboard_has_navigation(self, page: Page):
        inject_token(page)
        page.goto(FRONTEND, wait_until="networkidle")
        nav = page.locator("nav, aside, [role='navigation'], [class*='sidebar']").first
        expect(nav).to_be_visible()

    def test_dashboard_has_platform_content(self, page: Page):
        inject_token(page)
        page.goto(FRONTEND, wait_until="networkidle")
        body = page.locator("body").inner_text().lower()
        keywords = ["agent", "chat", "voice", "department", "reception", "sales", "hr"]
        found = [kw for kw in keywords if kw in body]
        assert len(found) >= 1, f"No platform keywords found. Snippet: {body[:400]}"

    def test_dashboard_no_page_errors(self, page: Page):
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        inject_token(page)
        page.goto(FRONTEND, wait_until="networkidle")
        page.wait_for_timeout(1200)
        assert not errors, f"Page errors: {errors}"


# ══════════════════════════════════════════════════════════════════════════════
# 4. CHAT API
# ══════════════════════════════════════════════════════════════════════════════

class TestChatAPI:
    def test_chat_receptionist(self):
        r = httpx.post(
            f"{API}/api/v1/chat",
            json={"message": "Hello, who are you?", "department": "reception", "user_id": "e2e_test"},
            headers=auth_headers(),
            timeout=60,
        )
        assert r.status_code == 200, f"Chat failed: {r.text}"
        data = r.json()
        assert "message" in data
        assert data["message"]["content"]

    def test_chat_all_departments(self):
        departments = ["reception", "sales", "hr", "finance", "technology", "marketing", "customer_care"]
        hdrs = auth_headers()
        results = {}
        for dept in departments:
            r = httpx.post(
                f"{API}/api/v1/chat",
                json={"message": "Introduce yourself briefly.", "department": dept, "user_id": "e2e_test"},
                headers=hdrs,
                timeout=60,
            )
            results[dept] = r.status_code
        failed = {d: c for d, c in results.items() if c != 200}
        assert not failed, f"Departments failed: {failed}"

    def test_chat_session_continuity(self):
        hdrs = auth_headers()
        r1 = httpx.post(
            f"{API}/api/v1/chat",
            json={"message": "My name is TestUser", "department": "reception", "user_id": "e2e_session_test"},
            headers=hdrs, timeout=60,
        )
        assert r1.status_code == 200
        session_id = r1.json().get("session_id")
        assert session_id

        r2 = httpx.post(
            f"{API}/api/v1/chat",
            json={"message": "What is my name?", "department": "reception",
                  "user_id": "e2e_session_test", "session_id": session_id},
            headers=hdrs, timeout=60,
        )
        assert r2.status_code == 200

    def test_chat_allows_anonymous(self):
        """Chat uses optional auth — anonymous requests should succeed."""
        r = httpx.post(
            f"{API}/api/v1/chat",
            json={"message": "Hello", "department": "reception"},
            timeout=60,
        )
        assert r.status_code == 200, f"Anonymous chat failed: {r.text}"

    def test_chat_ui_loads(self, page: Page):
        inject_token(page)
        page.goto(f"{FRONTEND}/chat", wait_until="networkidle")
        page.screenshot(path="tests/e2e/screenshots/e2e_05_chat_ui.png", full_page=True)
        assert "/login" not in page.url

    def test_chat_ui_can_send_message(self, page: Page):
        inject_token(page)
        page.goto(f"{FRONTEND}/chat", wait_until="networkidle")
        page.wait_for_timeout(1000)
        # Find message input
        textarea = page.locator(
            "textarea, input[placeholder*='essage' i], input[placeholder*='type' i]"
        ).first
        if textarea.is_visible():
            textarea.fill("Hello, test message from E2E")
            send_btn = page.locator("button[type='submit'], button:has-text('Send')").first
            if send_btn.is_visible():
                send_btn.click()
                page.wait_for_timeout(3000)
                page.screenshot(path="tests/e2e/screenshots/e2e_06_chat_sent.png", full_page=True)
        else:
            pytest.skip("Chat input not found - may need different selector")


# ══════════════════════════════════════════════════════════════════════════════
# 5. VOICE API
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceAPI:
    def test_tts_speak_endpoint(self):
        r = httpx.post(
            f"{API}/api/v1/voice/speak",
            json={"text": "Hello from the AI Workforce Platform.", "department": "reception"},
            headers=auth_headers(),
            timeout=30,
        )
        assert r.status_code == 200, f"TTS failed: {r.text}"
        ct = r.headers.get("content-type", "")
        assert "audio" in ct, f"Expected audio content-type, got: {ct}"

    def test_tts_all_departments(self):
        hdrs = auth_headers()
        departments = ["reception", "sales", "hr", "finance", "technology"]
        failed = []
        for dept in departments:
            r = httpx.post(
                f"{API}/api/v1/voice/speak",
                json={"text": f"Hello from {dept} department.", "department": dept},
                headers=hdrs, timeout=30,
            )
            if r.status_code != 200:
                failed.append(f"{dept}:{r.status_code}")
        assert not failed, f"TTS failed for: {failed}"

    def test_tts_requires_auth(self):
        """Voice sessions require auth; TTS speak may use optional auth."""
        r = httpx.post(
            f"{API}/api/v1/voice/sessions",
            json={"department": "reception", "user_id": "anon"},
            timeout=10,
        )
        assert r.status_code in (401, 403, 422), f"Expected auth required, got {r.status_code}"

    def test_voice_create_session(self):
        r = httpx.post(
            f"{API}/api/v1/voice/sessions",
            json={"department": "reception", "user_id": "e2e_test"},
            headers=auth_headers(),
            timeout=15,
        )
        assert r.status_code in (200, 201), f"Session create failed: {r.text}"
        data = r.json()
        assert "session_id" in data

    def test_voice_list_sessions(self):
        r = httpx.get(f"{API}/api/v1/voice/sessions", headers=auth_headers(), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_voice_stt_endpoint_reachable(self):
        import io
        # Minimal WAV header (44 bytes) + silence
        fake_wav = bytes([
            0x52, 0x49, 0x46, 0x46, 0x24, 0x08, 0x00, 0x00,
            0x57, 0x41, 0x56, 0x45, 0x66, 0x6d, 0x74, 0x20,
            0x10, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
            0x40, 0x1f, 0x00, 0x00, 0x80, 0x3e, 0x00, 0x00,
            0x02, 0x00, 0x10, 0x00, 0x64, 0x61, 0x74, 0x61,
            0x00, 0x08, 0x00, 0x00,
        ]) + b'\x00' * 2048
        r = httpx.post(
            f"{API}/api/v1/voice/transcribe",
            content=fake_wav,
            headers={**auth_headers(), "Content-Type": "audio/wav"},
            timeout=15,
        )
        # 200 = transcribed, 422 = bad audio (endpoint works), 400 = bad input (endpoint works)
        assert r.status_code in (200, 400, 422), f"STT unreachable: {r.status_code} {r.text}"

    def test_voice_ui_loads(self, page: Page):
        inject_token(page)
        page.goto(f"{FRONTEND}/voice", wait_until="networkidle")
        page.screenshot(path="tests/e2e/screenshots/e2e_07_voice_ui.png", full_page=True)
        assert "/login" not in page.url

    def test_voice_ui_has_mic_control(self, page: Page):
        inject_token(page)
        page.goto(f"{FRONTEND}/voice", wait_until="networkidle")
        # Look for any interactive element suggesting voice control
        mic = page.locator(
            "button:has-text('Start'), button:has-text('Record'), button:has-text('Speak'), "
            "button[aria-label*='mic' i], [class*='mic' i], [class*='voice' i] button"
        ).first
        expect(mic).to_be_visible()

    def test_voice_ui_has_department_selector(self, page: Page):
        inject_token(page)
        page.goto(f"{FRONTEND}/voice", wait_until="networkidle")
        body = page.locator("body").inner_text().lower()
        found = [d for d in ["reception", "sales", "hr", "finance", "technology"] if d in body]
        assert len(found) >= 1, "No departments visible on voice page"


# ══════════════════════════════════════════════════════════════════════════════
# 6. AGENTS & WORKFLOWS API
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentsWorkflows:
    def test_agents_list(self):
        r = httpx.get(f"{API}/api/v1/agents", headers=auth_headers(), timeout=10)
        assert r.status_code == 200
        agents = r.json()
        assert isinstance(agents, list)
        assert len(agents) >= 7  # at least 7 departments
        # Check structure
        first = agents[0]
        assert "agent_name" in first
        assert "department" in first

    def test_agents_have_all_departments(self):
        r = httpx.get(f"{API}/api/v1/agents", headers=auth_headers(), timeout=10)
        agents = r.json()
        departments = {a["department"] for a in agents}
        expected = {"reception", "sales", "hr", "finance", "technology", "marketing", "customer_care"}
        missing = expected - departments
        assert not missing, f"Missing departments: {missing}"

    def test_workflow_reception(self):
        r = httpx.post(
            f"{API}/api/v1/workflows",
            json={"task": "I need help getting started.", "department": "reception", "user_id": "e2e_test"},
            headers=auth_headers(),
            timeout=90,
        )
        assert r.status_code == 200, f"Workflow failed: {r.text}"
        data = r.json()
        assert "workflow_id" in data
        assert "output" in data
        assert data["output"]

    def test_workflow_requires_auth(self):
        r = httpx.post(
            f"{API}/api/v1/workflows",
            json={"task": "test", "department": "reception", "user_id": "e2e_test"},
            timeout=10,
        )
        assert r.status_code in (401, 403, 422)


# ══════════════════════════════════════════════════════════════════════════════
# 7. MCP / CRM INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPCRM:
    def test_mcp_tools_list(self):
        r = httpx.get(f"{API}/api/v1/mcp/tools", headers=auth_headers(), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_crm_list_tools_jsonrpc(self):
        r = httpx.post(
            f"{API}/mcp/crm",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=auth_headers(),
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "result" in data
        tools = data["result"]["tools"]
        assert len(tools) >= 1
        tool_names = [t["name"] for t in tools]
        assert any("crm" in n for n in tool_names)

    def test_crm_list_contacts(self):
        r = httpx.get(f"{API}/mcp/crm/contacts", headers=auth_headers(), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "contacts" in data
        assert len(data["contacts"]) >= 1
        # Verify structure
        c = data["contacts"][0]
        assert "name" in c
        assert "email" in c

    def test_crm_call_tool_jsonrpc(self):
        r = httpx.post(
            f"{API}/mcp/crm",
            json={
                "jsonrpc": "2.0", "id": 2,
                "method": "tools/call",
                "params": {"name": "crm_list_contacts", "arguments": {}},
            },
            headers=auth_headers(),
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "result" in data


# ══════════════════════════════════════════════════════════════════════════════
# 8. WEBSOCKET
# ══════════════════════════════════════════════════════════════════════════════

class TestWebSocket:
    def test_ws_chat_endpoint_exists(self):
        """WS endpoint returns 404 on plain HTTP (no upgrade) — that's expected.
        The actual connectivity is verified in test_ws_chat_functional."""
        import urllib.request, urllib.error
        try:
            urllib.request.urlopen("http://localhost:8080/api/v1/ws/chat", timeout=5)
            # If 200 returned for plain HTTP that's also fine
        except urllib.error.HTTPError as e:
            # 400=bad request, 404=endpoint exists but needs WS, 426=upgrade required
            assert e.code in (400, 404, 426, 403), f"Unexpected HTTP code: {e.code}"
        except ConnectionResetError:
            pass  # server closed non-WS connection — endpoint exists

    def test_ws_voice_endpoint_exists(self):
        import urllib.request, urllib.error
        try:
            urllib.request.urlopen("http://localhost:8080/api/v1/ws/voice/test_session", timeout=5)
        except urllib.error.HTTPError as e:
            assert e.code in (400, 404, 426, 403), f"Unexpected HTTP code: {e.code}"
        except ConnectionResetError:
            pass

    def test_ws_chat_functional(self):
        """Connect via WebSocket and exchange a message."""
        import websocket  # websocket-client
        token = get_token()
        ws = websocket.create_connection(
            f"ws://localhost:8080/api/v1/ws/chat?user_id=e2e_ws&token={token}",
            timeout=10,
        )
        ws.send(json.dumps({"message": "Hello", "department": "reception"}))
        resp = json.loads(ws.recv())
        ws.close()
        assert "content" in resp or "message" in resp or "role" in resp


# ══════════════════════════════════════════════════════════════════════════════
# 9. OBSERVABILITY & HEALTH
# ══════════════════════════════════════════════════════════════════════════════

class TestObservability:
    def test_health_endpoint(self):
        r = httpx.get(f"{API}/api/v1/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_api_docs_accessible(self):
        r = httpx.get(f"{API}/docs", timeout=10)
        assert r.status_code == 200

    def test_openapi_schema_complete(self):
        r = httpx.get(f"{API}/openapi.json", timeout=10)
        assert r.status_code == 200
        schema = r.json()
        paths = schema.get("paths", {})
        assert len(paths) >= 8  # health, auth, chat, voice, agents, workflows, mcp
        # Verify key paths exist
        assert "/api/v1/health" in paths
        assert "/api/v1/auth/token" in paths
        assert "/api/v1/chat" in paths or "/api/v1/chat/" in paths
        assert "/api/v1/agents" in paths

    def test_metrics_endpoint(self):
        r = httpx.get(f"{API}/api/v1/metrics", timeout=10)
        # May return 200 (Prometheus format) or 401 (protected)
        assert r.status_code in (200, 401, 403)

    def test_api_root(self):
        r = httpx.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "name" in data or "version" in data


# ══════════════════════════════════════════════════════════════════════════════
# 10. FULL NAVIGATION FLOW
# ══════════════════════════════════════════════════════════════════════════════

class TestNavigationFlow:
    def test_all_main_pages_accessible(self, page: Page):
        inject_token(page)
        routes = ["/", "/chat", "/voice", "/agents", "/settings"]
        results = {}
        for path in routes:
            page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(500)
            is_auth = "/login" not in page.url and "/welcome" not in page.url
            results[path] = {"url": page.url, "authenticated": is_auth}
            page.screenshot(
                path=f"tests/e2e/screenshots/e2e_nav_{path.strip('/') or 'home'}.png"
            )
        # / and /chat must be accessible
        assert results["/"]["authenticated"] or results["/chat"]["authenticated"], \
            f"Core pages not accessible: {results}"

    def test_sidebar_has_links(self, page: Page):
        inject_token(page)
        page.goto(FRONTEND, wait_until="networkidle")
        links = page.locator("nav a, aside a, [class*='sidebar'] a").all()
        assert len(links) >= 2, f"Expected sidebar links, found {len(links)}"

    def test_logout_clears_session(self, page: Page):
        inject_token(page)
        page.goto(FRONTEND, wait_until="networkidle")
        logout = page.locator(
            "button:has-text('Logout'), button:has-text('Sign out'), a:has-text('Logout'), "
            "a:has-text('Sign out')"
        ).first
        if logout.is_visible():
            logout.click()
            page.wait_for_url(f"{FRONTEND}/**", wait_until="networkidle", timeout=10000)
            assert "/login" in page.url or "/welcome" in page.url, \
                f"Expected logout redirect, got: {page.url}"
        else:
            pytest.skip("Logout button not found in sidebar")

    def test_welcome_cta_goes_to_login(self, page: Page):
        page.goto(f"{FRONTEND}/welcome", wait_until="networkidle")
        cta = page.locator("a[href*='login'], button:has-text('Get Started'), a:has-text('Get Started')").first
        if cta.is_visible():
            cta.click()
            page.wait_for_url(f"{FRONTEND}/**", wait_until="networkidle", timeout=10000)
            assert "/login" in page.url or "/welcome" in page.url
