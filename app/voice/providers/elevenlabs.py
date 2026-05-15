"""ElevenLabs streaming TTS provider."""

from __future__ import annotations

from typing import AsyncIterator

from app.core.config import settings
from app.core.exceptions import VoiceProviderError
from app.voice.providers.base import AudioChunk, TTSProvider


class ElevenLabsTTS(TTSProvider):
    name = "elevenlabs"

    def __init__(self, api_key: str | None = None, voice_id: str | None = None) -> None:
        self.api_key = api_key or settings.elevenlabs_api_key
        self.voice_id = voice_id or settings.elevenlabs_voice_id

    async def stream_synthesize(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        language: str = "en",
        sample_rate: int = 24000,
    ) -> AsyncIterator[AudioChunk]:
        if not self.api_key:
            raise VoiceProviderError("ElevenLabs API key not configured")
        try:
            from elevenlabs.client import AsyncElevenLabs  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise VoiceProviderError(f"elevenlabs SDK unavailable: {exc}") from exc

        client = AsyncElevenLabs(api_key=self.api_key)
        stream = client.text_to_speech.convert_as_stream(
            voice_id=voice_id or self.voice_id,
            optimize_streaming_latency=3,
            output_format="pcm_24000",
            text=text,
            model_id="eleven_turbo_v2_5",
        )
        async for chunk in stream:
            if chunk:
                yield AudioChunk(payload=chunk, sample_rate=sample_rate, encoding="pcm16")
