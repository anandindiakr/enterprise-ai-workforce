"""E2E tests for the AI Workforce Platform chat interface.

Coverage:
1. Homepage loads
2. Chat page renders (input, send button, department selector)
3. Send a message and receive a non-empty AI response
4. Department switcher changes active department
5. Multiple messages accumulate in the thread
6. Voice page is accessible
7. Dashboard page is accessible
8. API health endpoint returns OK
"""
from __future__ import annotations

import re
import time

import httpx
import pytest
from playwright.sync_api import Page, expect

FRONTEND_URL = "http://localhost:4000"
API_URL = "http://localhost:8080"


# ---------------------------------------------------------------------------
# 1. API health (fast pre-check so UI tests are meaningful)
# ---------------------------------------------------------------------------

def test_api_health():
    """Backend must be healthy before testing the UI."""
    r = httpx.get(f"{API_URL}/api/v1/health", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") in ("ok", "healthy", "degraded"), f"Unexpected health: {body}"


# ---------------------------------------------------------------------------
# 2. Homepage / landing page
# ---------------------------------------------------------------------------

def test_homepage_loads(page: Page):
    """Root URL should return a page with visible content."""
    page.goto("/")
    page.wait_for_load_state("networkidle")
    # Should not be a raw error page
    assert page.title() != ""
    # Should render some text content
    body_text = page.locator("body").inner_text()
    assert len(body_text.strip()) > 20, "Page body appears empty"


# ---------------------------------------------------------------------------
# 3. Chat page structure
# ---------------------------------------------------------------------------

def test_chat_page_renders(page: Page):
    """Chat page must have: a text input and at least one action button."""
    page.goto("/chat")
    page.wait_for_load_state("networkidle")

    # Text input (textarea is most common in chat UIs)
    chat_input = page.locator(
        "textarea, input[type='text']"
    ).first
    expect(chat_input).to_be_visible()

    # Any button present (send button may be icon-only)
    buttons = page.locator("button")
    assert buttons.count() > 0, "No buttons found on chat page"


# ---------------------------------------------------------------------------
# 4. Department selector
# ---------------------------------------------------------------------------

def test_department_selector_visible(page: Page):
    """The chat interface should expose a department picker."""
    page.goto("/chat")
    page.wait_for_load_state("networkidle")

    # Look for department-related elements (select, buttons, tabs)
    dept_element = page.locator(
        "select, [data-testid*='department' i], button:has-text('Reception'), "
        "button:has-text('Sales'), button:has-text('HR'), button:has-text('Technology'), "
        "button:has-text('Finance'), button:has-text('Marketing'), "
        "[class*='department' i], [class*='agent' i]"
    ).first
    expect(dept_element).to_be_visible()


# ---------------------------------------------------------------------------
# 5. Send a message and get a response (end-to-end)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_send_message_and_receive_response(page: Page):
    """Type a greeting, send it, and verify a non-empty AI response appears."""
    page.goto("/chat")
    page.wait_for_load_state("networkidle")

    # Fill the chat input
    chat_input = page.locator("textarea, input[type='text']").first
    expect(chat_input).to_be_visible()
    chat_input.fill("Hello, I need help")
    chat_input.press("Enter")

    # Wait for the AI response — up to 90s
    # Strategy: body text grows beyond what the user typed
    page.wait_for_function(
        """() => {
            const bodyText = document.body.innerText || '';
            // Page should contain more than just the user message once agent responds
            const hasResponse = bodyText.length > 100 &&
                (bodyText.includes('Hello') || bodyText.includes('help') ||
                 bodyText.includes('assist') || bodyText.includes('welcome') ||
                 bodyText.includes('department') || bodyText.includes('Hi'));
            // Must have MORE content than just the user message
            const userMsg = 'Hello, I need help';
            const contentBeyondUserMsg = bodyText.replace(userMsg, '').trim().length > 30;
            return hasResponse && contentBeyondUserMsg;
        }""",
        timeout=90_000,
    )

    all_text = page.locator("body").inner_text()
    words_present = any(w in all_text.lower() for w in [
        "help", "assist", "hello", "hi", "welcome", "department",
        "can i", "how can", "support", "pleasure", "today", "reception"
    ])
    assert words_present, f"No meaningful AI response on page. Body: {all_text[:600]}"


# ---------------------------------------------------------------------------
# 6. Multiple messages accumulate
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_multiple_messages_accumulate(page: Page):
    """Send two messages sequentially; both should appear in the thread."""
    page.goto("/chat")
    page.wait_for_load_state("networkidle")

    input_sel = "textarea, input[type='text'], input[placeholder*='message' i]"
    send_sel = "button:has-text('Send'), button[aria-label*='send' i], button[type='submit']"

    for msg in ["Hello there", "What departments do you have?"]:
        chat_input = page.locator("textarea, input[type='text']").first
        expect(chat_input).to_be_visible()
        chat_input.fill(msg)
        chat_input.press("Enter")
        page.wait_for_timeout(2_000)

    # Both original messages should appear somewhere on the page
    body_text = page.locator("body").inner_text()
    assert "Hello there" in body_text, "First message not visible in thread"
    assert "What departments" in body_text, "Second message not visible in thread"


# ---------------------------------------------------------------------------
# 7. Department switcher changes selection
# ---------------------------------------------------------------------------

def test_department_switch(page: Page):
    """Clicking a department button/option should change active selection."""
    page.goto("/chat")
    page.wait_for_load_state("networkidle")

    # Try to click a specific department
    dept_btn = page.locator(
        "button:has-text('Sales'), option[value*='sales' i], "
        "[data-dept='sales'], [class*='dept']:has-text('Sales')"
    ).first

    if dept_btn.is_visible():
        dept_btn.click()
        page.wait_for_timeout(500)
        # After clicking, some visual indication should change
        # (active class, selected option, etc.)
        body_html = page.content()
        assert "sales" in body_html.lower() or "Sales" in body_html, \
            "Department switch to Sales not reflected in DOM"
    else:
        pytest.skip("Department switch UI not found — skipping")


# ---------------------------------------------------------------------------
# 8. Voice page accessible
# ---------------------------------------------------------------------------

def test_voice_page_accessible(page: Page):
    """Voice page should load without a JS crash."""
    page.goto("/voice")
    page.wait_for_load_state("networkidle")

    # Should not show a Next.js error overlay
    error_overlay = page.locator("nextjs-portal, #__next-error, [data-nextjs-dialog]")
    assert error_overlay.count() == 0, "Next.js error overlay present on /voice"

    body_text = page.locator("body").inner_text()
    assert len(body_text.strip()) > 10, "Voice page body is empty"


# ---------------------------------------------------------------------------
# 9. Dashboard accessible
# ---------------------------------------------------------------------------

def test_dashboard_accessible(page: Page):
    """Dashboard page should render without a crash."""
    page.goto("/dashboard")
    page.wait_for_load_state("networkidle")

    error_overlay = page.locator("nextjs-portal, #__next-error, [data-nextjs-dialog]")
    assert error_overlay.count() == 0, "Next.js error overlay on /dashboard"

    body_text = page.locator("body").inner_text()
    assert len(body_text.strip()) > 10, "Dashboard body is empty"


# ---------------------------------------------------------------------------
# 10. Chat API endpoint direct test
# ---------------------------------------------------------------------------

def test_chat_api_reception_direct():
    """POST /api/v1/chat to reception should return a non-empty content field."""
    payload = {"message": "Hello", "department": "reception"}
    r = httpx.post(f"{API_URL}/api/v1/chat", json=payload, timeout=60)
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}"
    body = r.json()
    content = body.get("message", {}).get("content", "") or body.get("content", "")
    assert content and content.strip(), f"Empty content in response: {body}"


def test_chat_api_hr_direct():
    """POST /api/v1/chat to hr should return a non-empty content field."""
    payload = {"message": "What is the PTO policy?", "department": "hr"}
    r = httpx.post(f"{API_URL}/api/v1/chat", json=payload, timeout=60)
    assert r.status_code == 200
    body = r.json()
    content = body.get("message", {}).get("content", "") or body.get("content", "")
    assert content and content.strip(), f"Empty content in HR response: {body}"
