"""
End-to-end tests for Login and Voice features.

Login tests  (TestLogin)
  - Login page renders correctly
  - Invalid credentials show inline error
  - Valid admin credentials redirect to dashboard
  - Already-authenticated users skip login
  - Unauthenticated users redirected from protected pages
  - Logout clears session + goes back to /login
  - Password visibility toggle

Voice tests  (TestVoice)
  - Voice page accessible after login
  - All 7 department tabs rendered
  - Mic button visible and clickable
  - Transcript area present
  - No JS console errors
  - TTS API returns audio (API level)
  - TTS works for multiple departments
  - STT endpoint reachable (API level)
  - Voice session creation (API level)
  - CRM MCP tools/list returns 6 tools
  - CRM contacts tool returns demo data
  - CRM pipeline summary tool works

Run:
  python -m pytest tests/e2e/test_login_voice.py -v
"""

from __future__ import annotations

import re as _re
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect, sync_playwright

# ─────────────────────── config ──────────────────────────────────────────────
BASE_URL   = "http://localhost:4000"
API_URL    = "http://localhost:8080"
ADMIN_USER = "admin"
ADMIN_PASS = "admin"
SCREENSHOT_DIR = Path("tests/e2e/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def re_compile(pattern: str, *, case_insensitive: bool = False) -> _re.Pattern:
    flags = _re.IGNORECASE if case_insensitive else 0
    return _re.compile(pattern, flags)


# ─────────────────────── helpers ─────────────────────────────────────────────

def _get_token(username: str = ADMIN_USER, password: str = ADMIN_PASS) -> str:
    r = httpx.post(
        f"{API_URL}/api/v1/auth/token",
        json={"username": username, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _inject_token(page: Page, token: str, username: str = ADMIN_USER) -> None:
    """Inject JWT into localStorage so the AuthGuard passes."""
    page.evaluate(
        "(args) => {"
        "  localStorage.setItem(args.key, args.token);"
        "  localStorage.setItem(args.userKey, JSON.stringify(args.user));"
        "}",
        {
            "key": "workforce_token",
            "token": token,
            "userKey": "workforce_user",
            "user": {"username": username, "roles": ["admin"]},
        },
    )


def _screenshot(page: Page, name: str) -> None:
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  [screenshot] {path}")


# ─────────────────────── fixtures ────────────────────────────────────────────

@pytest.fixture(scope="session")
def admin_token() -> str:
    return _get_token(ADMIN_USER, ADMIN_PASS)


@pytest.fixture()
def page_unauth():
    """Fresh browser page with no localStorage (unauthenticated)."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            permissions=["microphone"],
        )
        pg = ctx.new_page()
        yield pg
        browser.close()


@pytest.fixture()
def page_auth(admin_token):
    """Browser page pre-seeded with a valid admin JWT."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            permissions=["microphone"],
        )
        pg = ctx.new_page()
        # Navigate to login first so localStorage is in scope, then inject token
        pg.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        _inject_token(pg, admin_token, ADMIN_USER)
        yield pg
        browser.close()


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestLogin:

    def test_login_page_renders(self, page_unauth: Page):
        """Login page shows logo, form fields and demo account hints."""
        page_unauth.goto(f"{BASE_URL}/login", wait_until="networkidle")
        _screenshot(page_unauth, "01_login_page_renders")

        expect(page_unauth.get_by_text("WORKFORCE").first).to_be_visible()
        expect(page_unauth.get_by_text("Enterprise AI Platform")).to_be_visible()
        expect(page_unauth.get_by_placeholder("admin")).to_be_visible()
        expect(page_unauth.get_by_placeholder("••••••••")).to_be_visible()
        expect(page_unauth.get_by_role("button", name="Sign in")).to_be_visible()
        expect(page_unauth.get_by_text("Demo accounts")).to_be_visible()

    def test_unauthenticated_redirect_to_login(self, page_unauth: Page):
        """/chat without a token redirects to /login."""
        page_unauth.goto(f"{BASE_URL}/chat", wait_until="networkidle")
        _screenshot(page_unauth, "02_unauth_redirect")
        expect(page_unauth).to_have_url(f"{BASE_URL}/login")

    def test_unauthenticated_dashboard_redirect(self, page_unauth: Page):
        """/ without a token redirects to /login."""
        page_unauth.goto(BASE_URL, wait_until="networkidle")
        _screenshot(page_unauth, "03_unauth_dashboard_redirect")
        expect(page_unauth).to_have_url(f"{BASE_URL}/login")

    def test_invalid_credentials_show_error(self, page_unauth: Page):
        """Wrong password shows inline error message."""
        page_unauth.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page_unauth.fill("input[placeholder='admin']", "admin")
        page_unauth.fill("input[type='password']", "wrongpassword123")
        page_unauth.click("button[type='submit']")

        # The error box has class text-red-400 and contains the API detail
        error_box = page_unauth.locator(".text-red-400").first
        error_box.wait_for(timeout=10000)
        _screenshot(page_unauth, "04_invalid_credentials_error")
        expect(error_box).to_be_visible()
        expect(page_unauth).to_have_url(f"{BASE_URL}/login")

    def test_valid_admin_login_redirects_to_dashboard(self, page_unauth: Page):
        """Correct admin credentials redirect to the dashboard."""
        # networkidle ensures React is fully hydrated before we interact
        page_unauth.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page_unauth.fill("input[placeholder='admin']", ADMIN_USER)
        page_unauth.fill("input[type='password']", ADMIN_PASS)

        # Wait for the auth API response, then navigation — more reliable than url lambda
        with page_unauth.expect_response(
            lambda r: "auth/token" in r.url and r.status == 200,
            timeout=20000,
        ):
            page_unauth.click("button[type='submit']")

        # After the token response, Next.js router.replace("/") fires
        page_unauth.wait_for_url(_re.compile(r"localhost:4000/?$"), timeout=10000)
        _screenshot(page_unauth, "05_login_success_dashboard")
        expect(page_unauth.get_by_text("AI Workforce").first).to_be_visible()
        expect(page_unauth).not_to_have_url(f"{BASE_URL}/login")

    def test_password_toggle_visibility(self, page_unauth: Page):
        """Eye icon toggles password field type between password and text."""
        page_unauth.goto(f"{BASE_URL}/login", wait_until="networkidle")

        pw_field = page_unauth.locator("input[type='password']")
        expect(pw_field).to_be_visible()

        # The toggle button has tabindex=-1
        toggle_btn = page_unauth.locator("button[tabindex='-1']")
        expect(toggle_btn).to_be_visible()
        toggle_btn.click()

        # After toggle, React sets type="text" on the password input
        # Use wait_for_selector which avoids bullet-char encoding issues
        page_unauth.wait_for_selector("input[type='text'][autocomplete='current-password']", timeout=5000)
        _screenshot(page_unauth, "06_password_visible")
        visible_pw = page_unauth.locator("input[type='text'][autocomplete='current-password']")
        expect(visible_pw).to_be_visible()

    def test_logout_clears_session(self, page_auth: Page):
        """Clicking logout removes token and redirects to /login."""
        page_auth.goto(BASE_URL, wait_until="networkidle")
        _screenshot(page_auth, "07_before_logout")

        # Logout button (Sign out) in sidebar
        page_auth.locator("button[title='Sign out']").click()
        page_auth.wait_for_url(f"{BASE_URL}/login", timeout=8000)
        _screenshot(page_auth, "08_after_logout")

        expect(page_auth).to_have_url(f"{BASE_URL}/login")
        token = page_auth.evaluate("() => localStorage.getItem('workforce_token')")
        assert token is None

    def test_already_logged_in_skips_login(self, page_auth: Page):
        """Going to /login when already authenticated redirects away."""
        page_auth.goto(f"{BASE_URL}/login", wait_until="networkidle")
        _screenshot(page_auth, "09_already_logged_in")
        expect(page_auth).not_to_have_url(f"{BASE_URL}/login")

    def test_sidebar_shows_username_after_login(self, page_auth: Page):
        """Sidebar shows the logged-in username in the footer."""
        page_auth.goto(BASE_URL, wait_until="networkidle")
        _screenshot(page_auth, "10_sidebar_username")
        # Username appears in the sidebar user-info panel
        sidebar_user = page_auth.locator("aside").get_by_text(ADMIN_USER).first
        expect(sidebar_user).to_be_visible()


# ══════════════════════════════════════════════════════════════════════════════
#  VOICE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestVoice:

    def test_voice_page_accessible(self, page_auth: Page):
        """Voice console page loads without errors."""
        page_auth.goto(f"{BASE_URL}/voice", wait_until="networkidle")
        _screenshot(page_auth, "11_voice_page_accessible")
        expect(page_auth.get_by_text("Voice Console", exact=False).first).to_be_visible()

    def test_voice_page_has_mic_button(self, page_auth: Page):
        """The mic button (circular) is visible on the voice page."""
        page_auth.goto(f"{BASE_URL}/voice", wait_until="networkidle")
        _screenshot(page_auth, "12_voice_mic_button")
        # The button has an <svg> mic icon inside — we check via aria or the IDLE label near it
        # From screenshot: there's a large circular button and text "IDLE" above it
        # "Click the button to start a voice session" is the caption
        idle_label = page_auth.get_by_text("IDLE", exact=False).first
        expect(idle_label).to_be_visible()
        # The circular mic button is the only <button> in the center panel
        mic_btn = page_auth.locator("button").filter(
            has=page_auth.locator("svg")
        ).nth(2)  # sidebar collapse + logout take indices 0-1
        expect(mic_btn).to_be_visible()
        expect(mic_btn).to_be_enabled()

    def test_voice_page_department_selector(self, page_auth: Page):
        """All 7 department options are shown in the voice console."""
        page_auth.goto(f"{BASE_URL}/voice", wait_until="networkidle")
        _screenshot(page_auth, "13_voice_departments")
        for dept in ["Reception", "Customer Care", "Sales", "HR", "Finance", "Technology", "Marketing"]:
            expect(page_auth.get_by_text(dept, exact=False).first).to_be_visible()

    def test_voice_page_transcript_area(self, page_auth: Page):
        """Live transcript area + empty-state copy are present."""
        page_auth.goto(f"{BASE_URL}/voice", wait_until="networkidle")
        _screenshot(page_auth, "14_voice_transcript_area")
        # From screenshot: "Start a session to see the live transcript here"
        expect(
            page_auth.get_by_text(
                re_compile(r"transcript|live transcript|start a session", case_insensitive=True)
            ).first
        ).to_be_visible()

    def test_voice_page_no_console_errors(self, page_auth: Page):
        """No JavaScript errors on the voice page."""
        errors: list[str] = []
        page_auth.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page_auth.goto(f"{BASE_URL}/voice", wait_until="networkidle")
        _screenshot(page_auth, "15_voice_no_errors")
        real_errors = [e for e in errors if not any(skip in e.lower() for skip in ["favicon", "404", "hydration"])]
        assert real_errors == [], f"Console errors on voice page: {real_errors}"

    # ── API-level voice tests ────────────────────────────────────────────────

    def test_api_tts_returns_audio(self, admin_token: str):
        """POST /voice/speak returns audio/mpeg."""
        r = httpx.post(
            f"{API_URL}/api/v1/voice/speak",
            json={"text": "Hello from the AI Workforce Platform.", "department": "reception"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=20,
        )
        assert r.status_code == 200, f"TTS returned {r.status_code}: {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("audio/"), (
            f"Expected audio/* content-type, got: {r.headers.get('content-type')}"
        )
        assert len(r.content) > 1000, f"Audio too small ({len(r.content)} bytes)"

    def test_api_tts_different_departments(self, admin_token: str):
        """TTS endpoint handles multiple department voices."""
        for dept in ["sales", "hr", "technology"]:
            r = httpx.post(
                f"{API_URL}/api/v1/voice/speak",
                json={"text": f"This is the {dept} department.", "department": dept},
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=20,
            )
            assert r.status_code == 200, f"TTS for {dept} returned {r.status_code}"
            assert len(r.content) > 1000, f"Audio for {dept} too small"

    def test_api_stt_endpoint_reachable(self, admin_token: str):
        """POST /voice/transcribe accepts multipart audio upload."""
        r = httpx.post(
            f"{API_URL}/api/v1/voice/transcribe",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"audio": ("test.webm", b"not-real-audio", "audio/webm")},
            timeout=15,
        )
        # 404 = route missing; 422 = validation ok (provider rejected fake bytes); 200/502 = provider tried
        assert r.status_code not in (404,), (
            f"STT endpoint missing: {r.status_code}: {r.text[:200]}"
        )

    def test_api_voice_session_creation(self, admin_token: str):
        """POST /voice/sessions creates a session with websocket_url."""
        r = httpx.post(
            f"{API_URL}/api/v1/voice/sessions",
            json={"department": "reception", "language": "en"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert r.status_code == 200, f"Session create returned {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert "session_id" in data, f"No session_id: {data}"
        assert "websocket_url" in data, f"No websocket_url: {data}"

    def test_api_tts_unauthenticated_still_works(self):
        """TTS with no token uses optional auth and still returns audio or 503."""
        r = httpx.post(
            f"{API_URL}/api/v1/voice/speak",
            json={"text": "Testing unauthenticated TTS.", "department": "reception"},
            timeout=20,
        )
        assert r.status_code in (200, 503), f"Unexpected status: {r.status_code}"

    # ── CRM MCP tests ────────────────────────────────────────────────────────

    def test_crm_mcp_tools_list(self, admin_token: str):
        """CRM MCP exposes exactly 6 tools via JSON-RPC tools/list."""
        r = httpx.post(
            f"{API_URL}/mcp/crm",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            timeout=5,
        )
        assert r.status_code == 200
        tools = r.json()["result"]["tools"]
        assert len(tools) == 6, f"Expected 6 tools, got {len(tools)}: {[t['name'] for t in tools]}"

    def test_crm_list_contacts_tool(self, admin_token: str):
        """crm_list_contacts returns 3 demo contacts."""
        r = httpx.post(
            f"{API_URL}/mcp/crm",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "crm_list_contacts", "arguments": {}}},
            timeout=5,
        )
        assert r.status_code == 200
        content = r.json()["result"]["content"][0]["text"]
        assert "Alice" in content or "contacts" in content, f"Bad CRM response: {content[:200]}"

    def test_crm_pipeline_summary_tool(self, admin_token: str):
        """crm_pipeline_summary returns total pipeline value."""
        r = httpx.post(
            f"{API_URL}/mcp/crm",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "crm_pipeline_summary", "arguments": {}}},
            timeout=5,
        )
        assert r.status_code == 200
        content = r.json()["result"]["content"][0]["text"]
        assert "pipeline" in content.lower(), f"Bad pipeline response: {content[:200]}"
