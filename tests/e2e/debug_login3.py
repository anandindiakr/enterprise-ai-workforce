from playwright.sync_api import sync_playwright
import time

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    # NO permissions — same as the working debug_login.py
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()

    responses = []
    pg.on("response", lambda r: responses.append((r.status, r.url)))

    pg.goto("http://localhost:4000/login", wait_until="domcontentloaded")
    pg.fill("input[placeholder='admin']", "admin")
    pg.fill("input[type='password']", "admin")
    print("Filled form, clicking submit...")
    pg.click("button[type='submit']")
    time.sleep(5)

    auth_hits = [x for x in responses if "auth" in x[1]]
    print("Auth API hits:", auth_hits)
    print("URL after 5s:", pg.url)
    token = pg.evaluate("() => localStorage.getItem('workforce_token')")
    print("Token:", (token[:40] + "...") if token else "None")
    browser.close()
