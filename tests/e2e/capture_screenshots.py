from playwright.sync_api import sync_playwright
import time, pathlib

SHOTS = pathlib.Path("tests/e2e/screenshots")
SHOTS.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()

    # Welcome / landing page
    pg.goto("http://localhost:4000/welcome", wait_until="networkidle")
    pg.screenshot(path=str(SHOTS / "welcome_hero.png"), full_page=False)
    pg.evaluate("window.scrollTo(0, 900)")
    time.sleep(0.4)
    pg.screenshot(path=str(SHOTS / "welcome_features.png"), full_page=False)
    pg.evaluate("window.scrollTo(0, 2000)")
    time.sleep(0.4)
    pg.screenshot(path=str(SHOTS / "welcome_departments.png"), full_page=False)
    pg.evaluate("window.scrollTo(0, 3200)")
    time.sleep(0.4)
    pg.screenshot(path=str(SHOTS / "welcome_who.png"), full_page=False)

    # Full page
    pg.evaluate("window.scrollTo(0,0)")
    time.sleep(0.3)
    pg.screenshot(path=str(SHOTS / "welcome_full.png"), full_page=True)

    # Dashboard (need login first)
    pg.goto("http://localhost:4000/login", wait_until="networkidle")
    pg.fill("input[placeholder='admin']", "admin")
    pg.fill("input[type='password']", "admin")
    with pg.expect_response(lambda r: "auth/token" in r.url and r.status == 200, timeout=20000):
        pg.click("button[type='submit']")
    pg.wait_for_url("http://localhost:4000/", timeout=10000)
    pg.screenshot(path=str(SHOTS / "dashboard.png"), full_page=False)

    # Chat console
    pg.goto("http://localhost:4000/chat", wait_until="networkidle")
    pg.screenshot(path=str(SHOTS / "chat_console.png"), full_page=False)

    # Voice console
    pg.goto("http://localhost:4000/voice", wait_until="networkidle")
    pg.screenshot(path=str(SHOTS / "voice_console.png"), full_page=False)

    print("All screenshots saved to", SHOTS)
    browser.close()
