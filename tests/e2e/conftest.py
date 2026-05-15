"""Pytest + Playwright configuration for the AI Workforce Platform E2E tests."""
from __future__ import annotations

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

FRONTEND_URL = "http://localhost:4000"
API_URL = "http://localhost:8080"


@pytest.fixture(scope="session")
def browser_instance():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def context(browser_instance: Browser):
    ctx = browser_instance.new_context(
        viewport={"width": 1280, "height": 800},
        base_url=FRONTEND_URL,
    )
    ctx.set_default_timeout(30_000)
    yield ctx
    ctx.close()


@pytest.fixture
def page(context: BrowserContext) -> Page:
    p = context.new_page()
    yield p
    p.close()
