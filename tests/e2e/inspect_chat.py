"""Inspect the chat DOM during/after message sending."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()

    # Capture all console messages
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text[:100]}"))
    page.on("pageerror", lambda err: logs.append(f"[PAGEERR] {err}"))

    page.goto("http://localhost:4000/chat")
    page.wait_for_load_state("networkidle")

    # Take screenshot of initial state
    page.screenshot(path="tests/e2e/screenshots/chat_initial.png", full_page=True)

    # Print all interactive elements
    print("=== INITIAL DOM ===")
    for sel in ["textarea", "input[type='text']", "input", "button"]:
        els = page.query_selector_all(sel)
        for e in els[:5]:
            print(f"  {sel}: text={repr(e.inner_text()[:40])} placeholder={e.get_attribute('placeholder')} disabled={e.get_attribute('disabled')}")

    # Find and fill the input
    chat_input = page.locator("textarea, input[type='text']").first
    print(f"\nInput found: {chat_input.is_visible()}")
    chat_input.fill("Hello, I need help")
    page.screenshot(path="tests/e2e/screenshots/chat_filled.png")

    # Send via Enter
    chat_input.press("Enter")
    print("Sent Enter key")
    page.screenshot(path="tests/e2e/screenshots/chat_sent.png")

    # Wait 2s and check DOM
    page.wait_for_timeout(2000)
    page.screenshot(path="tests/e2e/screenshots/chat_after_send.png")

    # Print message containers
    print("\n=== AFTER SEND - KEY ELEMENTS ===")
    for sel in [
        "[class*='message']", "[class*='bubble']", "[class*='chat']",
        "ul li", "div > p", "[role='log']", "[role='listitem']",
        "[data-role]", "[class*='user']", "[class*='agent']",
        "[class*='assistant']", "[class*='response']"
    ]:
        els = page.query_selector_all(sel)
        if els:
            print(f"\n  {sel} ({len(els)} found):")
            for e in els[:3]:
                text = e.inner_text()[:80].strip()
                cls = (e.get_attribute("class") or "")[:60]
                if text:
                    print(f"    text={repr(text)} class={cls}")

    # Check if input is still visible/enabled
    inputs = page.query_selector_all("textarea, input[type='text']")
    print(f"\n=== INPUT STATE AFTER SEND ===")
    for i in inputs:
        print(f"  visible={i.is_visible()} disabled={i.get_attribute('disabled')} value={repr(i.input_value()[:30])}")

    print("\n=== CONSOLE LOGS ===")
    for l in logs[-10:]:
        print(f"  {l}")

    # Get full HTML of main content area
    main_html = page.locator("main, [class*='chat'], [class*='main'], body > div").first.inner_html()
    print(f"\n=== MAIN HTML SNIPPET ===\n{main_html[:2000]}")

    ctx.close()
    browser.close()
