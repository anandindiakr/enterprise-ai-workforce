"""Secrets service: loads DB-persisted API keys into os.environ on startup."""
from __future__ import annotations

import os

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import get_all_secrets
from app.api.routes.settings import ENV_MAP


async def load_secrets_to_env(db: AsyncSession) -> None:
    """Pull all saved secrets from DB and set them in os.environ.

    DB values take priority over empty env vars but never overwrite
    already-set env vars (so Docker/K8s secrets still win).
    """
    try:
        secrets = await get_all_secrets(db)
        applied = 0
        for k, v in secrets.items():
            if not v:
                continue
            env_key = ENV_MAP.get(k, k.upper())
            if not os.environ.get(env_key):
                os.environ[env_key] = v
                applied += 1
        if applied:
            logger.info("Loaded {} API key(s) from DB secrets store.", applied)
    except Exception as exc:
        logger.warning("Could not load DB secrets (table may not exist yet): {}", exc)
