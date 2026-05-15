"""Google Cloud Speech (STT/TTS) adapter -- extension point."""

from __future__ import annotations

from typing import AsyncIterator

from app.core.exceptions import VoiceProviderError
from app.voice.providers.base import AudioChunk, STTProvider, TTSProvider


class GoogleSTT(STTProvider):
    name = "google"

    async def stream_transcribe(
        self, audio: AsyncIterator[AudioChunk], *, language: str = "en-US"
    ) -> AsyncIterator[dict]:
        raise VoiceProviderError("GoogleSTT not implemented in scaffold")
        if False:  # pragma: no cover
            yield {}


class GoogleTTS(TTSProvider):
    name = "google"

    async def stream_synthesize(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        language: str = "en-US",
        sample_rate: int = 24000,
    ) -> AsyncIterator[AudioChunk]:
        raise VoiceProviderError("GoogleTTS not implemented in scaffold")
        if False:  # pragma: no cover
            yield AudioChunk(payload=b"")
