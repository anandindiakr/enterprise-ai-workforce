"""OpenAI Realtime full-duplex provider.

Implements the WebSocket realtime API. The session forwards audio frames in,
yields events out (audio deltas, transcript deltas, turn boundaries), and
supports server-side VAD with interruption.
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import AsyncIterator

from app.core.config import settings
from app.core.exceptions import VoiceProviderError
from app.core.logging import logger
from app.voice.providers.base import AudioChunk, RealtimeProvider, RealtimeSession


_WS_URL = "wss://api.openai.com/v1/realtime?model={model}"


class _OpenAIRealtimeSession(RealtimeSession):
    def __init__(self, ws, out_queue: asyncio.Queue[dict]) -> None:
        self._ws = ws
        self._out: asyncio.Queue[dict] = out_queue
        self._closed = False
        self._reader = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    event = json.loads(raw)
                except Exception:
                    continue
                await self._out.put(event)
        except Exception as exc:  # pragma: no cover
            logger.warning("OpenAI realtime read loop ended: {}", exc)
        finally:
            await self._out.put({"type": "session.closed"})

    async def send_audio(self, chunk: AudioChunk) -> None:
        if self._closed:
            return
        b64 = base64.b64encode(chunk.payload).decode("ascii")
        await self._ws.send(
            json.dumps({"type": "input_audio_buffer.append", "audio": b64})
        )

    async def send_text(self, text: str) -> None:
        await self._ws.send(
            json.dumps(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": text}],
                    },
                }
            )
        )
        await self._ws.send(json.dumps({"type": "response.create"}))

    async def events(self) -> AsyncIterator[dict]:
        while True:
            event = await self._out.get()
            yield event
            if event.get("type") == "session.closed":
                break

    async def interrupt(self) -> None:
        await self._ws.send(json.dumps({"type": "response.cancel"}))

    async def close(self) -> None:
        self._closed = True
        try:
            await self._ws.close()
        except Exception:
            pass
        if not self._reader.done():
            self._reader.cancel()


class OpenAIRealtimeProvider(RealtimeProvider):
    name = "openai_realtime"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_realtime_model

    async def open_session(
        self,
        *,
        system_prompt: str,
        voice_id: str | None = None,
        language: str = "en",
    ) -> RealtimeSession:
        if not self.api_key:
            raise VoiceProviderError("OPENAI_API_KEY not configured")

        try:
            import websockets  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise VoiceProviderError(f"websockets package unavailable: {exc}") from exc

        url = _WS_URL.format(model=self.model)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        ws = await websockets.connect(url, additional_headers=headers, max_size=None)

        session_update = {
            "type": "session.update",
            "session": {
                "instructions": system_prompt,
                "modalities": ["audio", "text"],
                "voice": voice_id or "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {"type": "server_vad", "threshold": 0.5},
                "input_audio_transcription": {"model": "whisper-1", "language": language},
            },
        }
        await ws.send(json.dumps(session_update))
        out_q: asyncio.Queue[dict] = asyncio.Queue()
        return _OpenAIRealtimeSession(ws, out_q)
