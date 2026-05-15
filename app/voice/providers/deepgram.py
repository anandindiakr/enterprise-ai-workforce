"""Deepgram streaming STT provider."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from app.core.config import settings
from app.core.exceptions import VoiceProviderError
from app.core.logging import logger
from app.voice.providers.base import AudioChunk, STTProvider


class DeepgramSTT(STTProvider):
    """Wrapper around Deepgram's Nova streaming API."""

    name = "deepgram"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.deepgram_api_key

    async def stream_transcribe(
        self, audio: AsyncIterator[AudioChunk], *, language: str = "en"
    ) -> AsyncIterator[dict]:
        if not self.api_key:
            raise VoiceProviderError("Deepgram API key not configured")
        try:
            from deepgram import (  # type: ignore
                DeepgramClient,
                LiveOptions,
                LiveTranscriptionEvents,
            )
        except Exception as exc:  # pragma: no cover
            raise VoiceProviderError(f"deepgram-sdk unavailable: {exc}") from exc

        client = DeepgramClient(self.api_key)
        connection = client.listen.asynclive.v("1")  # type: ignore[attr-defined]
        out_queue: asyncio.Queue[dict] = asyncio.Queue()

        async def _on_message(_, result, **__):  # noqa: ANN001
            try:
                alt = result.channel.alternatives[0]
                await out_queue.put(
                    {
                        "text": alt.transcript,
                        "is_final": bool(result.is_final),
                        "confidence": getattr(alt, "confidence", None),
                        "language": language,
                    }
                )
            except Exception:
                logger.debug("Deepgram payload parse error")

        connection.on(LiveTranscriptionEvents.Transcript, _on_message)

        await connection.start(
            LiveOptions(
                model="nova-2",
                language=language,
                smart_format=True,
                interim_results=True,
                encoding="linear16",
                sample_rate=16000,
                vad_events=True,
            )
        )

        async def _pump_audio() -> None:
            async for chunk in audio:
                await connection.send(chunk.payload)
            await connection.finish()

        pump_task = asyncio.create_task(_pump_audio())
        try:
            while True:
                done, _ = await asyncio.wait(
                    {asyncio.create_task(out_queue.get()), pump_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                got_event = False
                for t in done:
                    res = t.result() if not t.exception() else None
                    if isinstance(res, dict):
                        got_event = True
                        yield res
                if pump_task.done() and out_queue.empty():
                    break
                if not got_event and pump_task.done():
                    break
        finally:
            if not pump_task.done():
                pump_task.cancel()
