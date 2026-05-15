from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.goto("http://localhost:4000/chat")
    page.wait_for_load_state("networkidle")
    page.locator("textarea, input[type='text']").first.fill("Hello, what can you help me with today?")
    page.locator("textarea, input[type='text']").first.press("Enter")
    page.wait_for_function(
        "() => document.body.innerText.length > 80",
        timeout=90000
    )
    page.wait_for_timeout(1500)
    page.screenshot(path="tests/e2e/screenshots/chat_working.png", full_page=True)
    print("Screenshot saved")
    ctx.close()
    b.close()
