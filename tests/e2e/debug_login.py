from playwright.sync_api import sync_playwright
import time

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    log = []
    page.on("console", lambda m: log.append(f"[{m.type}] {m.text}"))
    page.on("response", lambda r: log.append(f"[HTTP {r.status}] {r.url}"))

    page.goto("http://localhost:4000/login", wait_until="domcontentloaded")
    page.fill("input[placeholder='admin']", "admin")
    page.fill("input[type='password']", "admin")
    page.screenshot(path="tests/e2e/screenshots/debug_before_submit.png", full_page=True)
    page.click("button[type='submit']")

    time.sleep(8)

    page.screenshot(path="tests/e2e/screenshots/debug_after_submit.png", full_page=True)
    print("URL after 8s:", page.url)

    token = page.evaluate("() => localStorage.getItem('workforce_token')")
    print("Token in localStorage:", (token[:40] + "...") if token else "None")

    print("\n--- Network log ---")
    for entry in log[-25:]:
        print(entry)

    browser.close()
