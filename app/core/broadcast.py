"""
Simple in-process async pub/sub broadcast bus.

Subscribers register an asyncio.Queue; publishers push JSON-serialisable
dicts.  The bus is intentionally process-local (no Redis dependency) and
is used for real-time UI push over the /ws/events WebSocket endpoint.

Usage
-----
    # publisher
    from app.core.broadcast import bus
    await bus.publish("escalations", {"type": "new_escalation", ...})

    # subscriber (in a WebSocket handler)
    async with bus.subscribe("escalations") as q:
        data = await q.get()
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator


class _Bus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        """Push *payload* to all current subscribers of *channel*."""
        async with self._lock:
            queues = list(self._subs.get(channel, []))
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # slow consumer — drop frame rather than block

    @asynccontextmanager
    async def subscribe(
        self, channel: str, maxsize: int = 64
    ) -> AsyncGenerator[asyncio.Queue[dict[str, Any]], None]:
        """Context-manager that yields a Queue and cleans up on exit."""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
        async with self._lock:
            self._subs[channel].append(q)
        try:
            yield q
        finally:
            async with self._lock:
                try:
                    self._subs[channel].remove(q)
                except ValueError:
                    pass


# Module-level singleton
bus = _Bus()
