"""Quick inspector script to grab DOM snapshots for debugging."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})

    # --- Chat page ---
    page = ctx.new_page()
    page.goto("http://localhost:4000/chat")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="tests/e2e/screenshots/chat_page.png", full_page=True)

    # Print all buttons
    buttons = page.query_selector_all("button")
    print("=== BUTTONS ON /chat ===")
    for b in buttons:
        print(f"  text={repr(b.inner_text()[:60])} aria={b.get_attribute('aria-label')} class={b.get_attribute('class')[:60] if b.get_attribute('class') else ''}")

    # Print all inputs
    inputs = page.query_selector_all("input, textarea")
    print("\n=== INPUTS ON /chat ===")
    for i in inputs:
        print(f"  tag={i.evaluate('el => el.tagName')} placeholder={i.get_attribute('placeholder')} class={i.get_attribute('class')[:60] if i.get_attribute('class') else ''}")

    page.close()

    # --- Voice page ---
    page2 = ctx.new_page()
    # Capture console errors
    errors = []
    page2.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
    page2.on("pageerror", lambda err: errors.append(f"[PAGE_ERR] {err}"))
    page2.goto("http://localhost:4000/voice")
    page2.wait_for_load_state("networkidle")
    page2.screenshot(path="tests/e2e/screenshots/voice_page.png", full_page=True)
    print("\n=== VOICE PAGE ERRORS ===")
    for e in errors:
        print(f"  {e[:200]}")
    
    # Print error overlay text
    overlay = page2.locator("nextjs-portal")
    if overlay.count() > 0:
        print("\n=== NEXT.JS ERROR OVERLAY TEXT ===")
        print(overlay.first.inner_text()[:800])

    page2.close()
    ctx.close()
    browser.close()
