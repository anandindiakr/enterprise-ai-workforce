"""In-process cache for company branding settings.

The cache is populated lazily on the first agent call and invalidated
whenever the operator saves changes via the Settings → Company & Agents UI.
It avoids a DB round-trip on every chat/voice turn.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings as cfg

_CACHE_TTL_SECONDS = 300  # 5 min — stale entries are refreshed automatically


@dataclass
class CompanyBranding:
    company_name: str = "AlgoWorkforce"
    company_tagline: str = "Your AI-Powered Enterprise Workforce"
    company_website: str = ""
    greeting_script: str = ""
    # {"sales": {"display_name": "Alex", "script": "Hello …"}, ...}
    agent_overrides: dict[str, Any] = field(default_factory=dict)


# tenant_id → (branding, loaded_at)
_cache: dict[str, tuple[CompanyBranding, float]] = {}
_locks: dict[str, asyncio.Lock] = {}


def _is_fresh(tenant_id: str) -> bool:
    entry = _cache.get(tenant_id)
    if entry is None:
        return False
    _, loaded_at = entry
    return (time.monotonic() - loaded_at) < _CACHE_TTL_SECONDS


def invalidate_company_cache(tenant_id: str = "default") -> None:
    """Force the next call to reload from the database."""
    _cache.pop(tenant_id, None)


def get_cached_branding_sync(tenant_id: str = "default") -> CompanyBranding | None:
    """Return cached branding if fresh, else None (caller must do async refresh)."""
    if _is_fresh(tenant_id):
        branding, _ = _cache[tenant_id]
        return branding
    return None


async def get_company_branding(tenant_id: str = "default") -> CompanyBranding:
    """Async-safe fetch with per-tenant lock to prevent cache stampedes."""
    if _is_fresh(tenant_id):
        branding, _ = _cache[tenant_id]
        return branding

    lock = _locks.setdefault(tenant_id, asyncio.Lock())
    async with lock:
        # Double-check after acquiring lock.
        if _is_fresh(tenant_id):
            branding, _ = _cache[tenant_id]
            return branding

        branding = await _load_from_db(tenant_id)
        _cache[tenant_id] = (branding, time.monotonic())
        return branding


async def _load_from_db(tenant_id: str) -> CompanyBranding:
    """Load branding from the database; fall back to env/config on any error."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.crud import get_company_settings

        async with AsyncSessionLocal() as db:
            row = await get_company_settings(db, tenant_id)
            await db.commit()
            return CompanyBranding(
                company_name=row.company_name or cfg.company_name,
                company_tagline=row.company_tagline or cfg.company_tagline,
                company_website=row.company_website or cfg.company_website,
                greeting_script=row.greeting_script or cfg.agent_greeting_script,
                agent_overrides=row.agent_overrides or {},
            )
    except Exception:
        # Graceful degradation — use env/config values so agents still work.
        return CompanyBranding(
            company_name=cfg.company_name,
            company_tagline=cfg.company_tagline,
            company_website=cfg.company_website,
            greeting_script=cfg.agent_greeting_script,
        )
