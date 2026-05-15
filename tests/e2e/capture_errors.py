from playwright.sync_api import sync_playwright

errors = []
console_msgs = []

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text[:200]}"))

    page.goto("http://localhost:4000/chat")
    page.wait_for_load_state("networkidle")

    inp = page.locator("textarea, input[type='text']").first
    inp.fill("Hello")
    inp.press("Enter")
    page.wait_for_timeout(5000)

    print("=== PAGE ERRORS ===")
    for e in errors:
        print(f"  {e[:300]}")

    print("\n=== CONSOLE ERRORS ===")
    for m in console_msgs:
        if "error" in m.lower() or "warn" in m.lower() or "unhandled" in m.lower():
            print(f"  {m[:300]}")

    print("\n=== FULL PAGE HTML (1500 chars) ===")
    print(page.content()[:1500])

    ctx.close()
    b.close()
