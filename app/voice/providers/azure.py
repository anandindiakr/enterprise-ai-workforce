"""Azure Cognitive Services Speech (STT/TTS) adapter."""

from __future__ import annotations

from typing import AsyncIterator

from app.core.config import settings
from app.core.exceptions import VoiceProviderError
from app.voice.providers.base import AudioChunk, STTProvider, TTSProvider


class AzureSTT(STTProvider):
    name = "azure"

    def __init__(self) -> None:
        self.key = settings.azure_speech_key
        self.region = settings.azure_speech_region

    async def stream_transcribe(
        self, audio: AsyncIterator[AudioChunk], *, language: str = "en-US"
    ) -> AsyncIterator[dict]:
        if not self.key:
            raise VoiceProviderError("Azure speech key not configured")
        # The official azure-cognitiveservices-speech SDK is sync-only; production
        # deployments typically run it in a worker thread. Left as an extension
        # point to keep this scaffold dependency-light.
        raise VoiceProviderError("AzureSTT.stream_transcribe not yet implemented in scaffold")
        if False:  # pragma: no cover - to satisfy generator typing
            yield {}


class AzureTTS(TTSProvider):
    name = "azure"

    async def stream_synthesize(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        language: str = "en-US",
        sample_rate: int = 24000,
    ) -> AsyncIterator[AudioChunk]:
        raise VoiceProviderError("AzureTTS.stream_synthesize not yet implemented in scaffold")
        if False:  # pragma: no cover
            yield AudioChunk(payload=b"")
