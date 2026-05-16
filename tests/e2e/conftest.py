import pytest
from playwright.sync_api import Page

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
