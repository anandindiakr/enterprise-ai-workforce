"""Redis-backed short-term conversational memory.

Stores per-session message history with TTL, plus simple key-value scratch
space for in-flight workflow state.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import Message

_DEFAULT_TTL = timedelta(hours=24)
_HISTORY_LIMIT = 200


class ShortTermMemory:
    """Per-session message log + scratch KV store backed by Redis."""

    def __init__(self, url: str | None = None) -> None:
        self._url = url or settings.redis_url
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        if self._client is None:
            self._client = redis.from_url(self._url, decode_responses=True)
            await self._client.ping()
            logger.info("ShortTermMemory connected to {}", self._url)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("ShortTermMemory not connected")
        return self._client

    # ---- Message log ---------------------------------------------------

    @staticmethod
    def _history_key(session_id: str) -> str:
        return f"workforce:history:{session_id}"

    async def append_message(
        self, session_id: str, message: Message, ttl: timedelta = _DEFAULT_TTL
    ) -> None:
        key = self._history_key(session_id)
        await self.client.rpush(key, message.model_dump_json())
        await self.client.ltrim(key, -_HISTORY_LIMIT, -1)
        await self.client.expire(key, int(ttl.total_seconds()))

    async def get_history(self, session_id: str, limit: int = 50) -> list[Message]:
        key = self._history_key(session_id)
        raw = await self.client.lrange(key, -limit, -1)
        return [Message.model_validate_json(item) for item in raw]

    async def clear_session(self, session_id: str) -> None:
        await self.client.delete(self._history_key(session_id))

    # ---- Scratch KV ----------------------------------------------------

    async def set_state(
        self, session_id: str, key: str, value: Any, ttl: timedelta = _DEFAULT_TTL
    ) -> None:
        await self.client.set(
            f"workforce:state:{session_id}:{key}",
            json.dumps(value, default=str),
            ex=int(ttl.total_seconds()),
        )

    async def get_state(self, session_id: str, key: str) -> Any | None:
        raw = await self.client.get(f"workforce:state:{session_id}:{key}")
        return json.loads(raw) if raw else None


# Singleton accessor (initialized in app lifespan)
_short_term: ShortTermMemory | None = None


def short_term_memory() -> ShortTermMemory:
    global _short_term
    if _short_term is None:
        _short_term = ShortTermMemory()
    return _short_term
