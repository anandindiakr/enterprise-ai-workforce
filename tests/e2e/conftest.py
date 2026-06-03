"""conftest.py – e2e suite configuration.

Playwright is optional; if it is not installed the file simply skips the
browser-fixture definitions so that the HTTP/WebSocket tests can still run.
"""
import pytest

try:
    from playwright.sync_api import Page as _Page  # noqa: F401

    @pytest.fixture(scope="session")
    def browser_context_args(browser_context_args):
        return {**browser_context_args, "ignore_https_errors": True}

    @pytest.fixture
    def page(browser):
        ctx = browser.new_context(ignore_https_errors=True)
        pg  = ctx.new_page()
        yield pg
        pg.close()
        ctx.close()

except ModuleNotFoundError:
    pass  # Playwright not installed — browser tests will be skipped by pytest-playwright
