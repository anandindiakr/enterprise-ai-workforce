"""Lightweight website content ingestion for the Products/Services catalog.

Beginner-friendly feature: an admin pastes a product/service page URL and the
platform fetches it, strips boilerplate (nav, scripts, styles, footers), and
extracts the readable text so it can be folded into the same knowledge-base
document that already backs the product. This keeps live call/chat latency
fast because scraping happens once (on save / manual re-scrape), not per
query.

Never raises -- callers get a result object with ``ok`` / ``error`` so a
failed scrape (site down, blocked, timeout) never blocks saving the product.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.core.logging import logger

_MAX_CHARS = 6000
# Keep the scraped blob bounded so the KB embedding / prompt stays fast and
# doesn't blow past model context limits.

_TIMEOUT = 12.0
_USER_AGENT = (
    "Mozilla/5.0 (compatible; AIWorkforceBot/1.0; "
    "+https://github.com/) AI-Workforce-Knowledge-Ingestor"
)

_STRIP_TAGS = ("script", "style", "noscript", "nav", "footer", "header", "svg", "form", "iframe")


@dataclass
class ScrapeResult:
    ok: bool
    text: str = ""
    title: str | None = None
    error: str | None = None


def _clean_text(soup: BeautifulSoup) -> str:
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    # Collapse repeated whitespace left over from get_text()
    joined = "\n".join(lines)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip()


async def scrape_url(url: str) -> ScrapeResult:
    """Fetch ``url`` and return cleaned, human-readable text (capped length).

    Safe to call from a request handler -- all network/parsing errors are
    caught and returned as a structured failure rather than raised.
    """
    if not url or not url.strip():
        return ScrapeResult(ok=False, error="No URL provided")

    normalized = url.strip()
    if not normalized.lower().startswith(("http://", "https://")):
        normalized = f"https://{normalized}"

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.get(normalized)
            resp.raise_for_status()
    except httpx.TimeoutException:
        return ScrapeResult(ok=False, error="The website took too long to respond (timeout).")
    except httpx.HTTPStatusError as exc:
        return ScrapeResult(ok=False, error=f"Website returned an error (HTTP {exc.response.status_code}).")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Website scrape failed for {}: {}", normalized, exc)
        return ScrapeResult(ok=False, error="Could not reach that website. Check the URL and try again.")

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type and "text" not in content_type:
        return ScrapeResult(ok=False, error="That URL doesn't look like a webpage (unsupported content type).")

    try:
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception:  # noqa: BLE001
        soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    text = _clean_text(soup)

    if not text:
        return ScrapeResult(ok=False, error="No readable text found on that page.")

    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS].rsplit("\n", 1)[0] + "\n…"

    return ScrapeResult(ok=True, text=text, title=title)
