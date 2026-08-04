"""
Server-push WebSocket endpoint: /api/v1/ws/events

Clients connect and receive real-time JSON events published on named
channels (e.g. "escalations").  The client may optionally send a JSON
message ``{"channels": ["escalations","workflows"]}`` to filter channels
(defaults to all supported channels).

Protocol
--------
Client → server: ``{"channels": ["escalations"]}``   (optional filter)
Server → client: ``{"channel": "escalations", "data": {...}}``
Server → client: ``{"type": "ping"}``  every 20 s (keep-alive)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.broadcast import bus

logger = logging.getLogger(__name__)
router = APIRouter()

_SUPPORTED_CHANNELS = {"escalations", "workflows", "voice_sessions", "audit", "orchestration"}
_PING_INTERVAL = 20  # seconds


@router.websocket("/ws/events")
async def events_ws(ws: WebSocket) -> None:
    """Real-time event push channel."""
    await ws.accept()
    subscribed: set[str] = set(_SUPPORTED_CHANNELS)  # default: all channels

    # Optional: client sends preferred channels within first 3 s
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=3.0)
        payload = json.loads(raw)
        requested = set(payload.get("channels", []))
        if requested:
            subscribed = requested & _SUPPORTED_CHANNELS
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        pass  # keep defaults

    # Subscribe to all relevant channels
    queues: list[tuple[str, asyncio.Queue[dict[str, Any]]]] = []
    # We can't use async context managers across multiple channels easily,
    # so we manually manage subscriptions.
    for ch in subscribed:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        bus._subs[ch].append(q)  # noqa: SLF001  (internal access acceptable)
        queues.append((ch, q))

    async def _cleanup():
        for ch, q in queues:
            try:
                bus._subs[ch].remove(q)  # noqa: SLF001
            except ValueError:
                pass

    async def _ping_loop():
        while True:
            await asyncio.sleep(_PING_INTERVAL)
            try:
                await ws.send_json({"type": "ping"})
            except Exception:
                break

    async def _event_loop():
        while True:
            # Poll all queues in round-robin with a tiny sleep
            for ch, q in queues:
                try:
                    data = q.get_nowait()
                    await ws.send_json({"channel": ch, "data": data})
                except asyncio.QueueEmpty:
                    pass
            await asyncio.sleep(0.1)

    ping_task  = asyncio.create_task(_ping_loop())
    event_task = asyncio.create_task(_event_loop())

    try:
        # Keep running until the WebSocket disconnects
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                continue  # just keep alive
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        ping_task.cancel()
        event_task.cancel()
        await _cleanup()
