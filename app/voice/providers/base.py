"""Abstract base classes for voice providers (STT / TTS / Realtime).

Concrete providers (Deepgram, ElevenLabs, OpenAI Realtime, Azure, Google,
LiveKit, Twilio) implement these interfaces. The :class:`VoiceGateway`
selects providers via configuration at runtime.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass(slots=True)
class AudioChunk:
    """Raw audio frame travelling between client, providers, and agents."""

    payload: bytes
    sample_rate: int = 16000
    encoding: str = "pcm16"
    is_final: bool = False
    timestamp_ms: int = 0


# ---------------------------------------------------------------------------
# STT
# ---------------------------------------------------------------------------


class STTProvider(abc.ABC):
    name: str = "abstract-stt"

    @abc.abstractmethod
    async def stream_transcribe(
        self, audio: AsyncIterator[AudioChunk], *, language: str = "en"
    ) -> AsyncIterator[dict]:
        """Yield transcript events: ``{"text": str, "is_final": bool, ...}``."""


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------


class TTSProvider(abc.ABC):
    name: str = "abstract-tts"

    @abc.abstractmethod
    async def stream_synthesize(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        language: str = "en",
        sample_rate: int = 24000,
    ) -> AsyncIterator[AudioChunk]:
        """Stream synthesized audio frames."""


# ---------------------------------------------------------------------------
# Realtime (full duplex)
# ---------------------------------------------------------------------------


class RealtimeProvider(abc.ABC):
    """Full-duplex realtime provider (e.g. OpenAI Realtime, LiveKit Agents)."""

    name: str = "abstract-realtime"

    @abc.abstractmethod
    async def open_session(
        self,
        *,
        system_prompt: str,
        voice_id: str | None = None,
        language: str = "en",
    ) -> "RealtimeSession":
        """Create a new bidirectional realtime session."""


class RealtimeSession(abc.ABC):
    @abc.abstractmethod
    async def send_audio(self, chunk: AudioChunk) -> None: ...

    @abc.abstractmethod
    async def send_text(self, text: str) -> None: ...

    @abc.abstractmethod
    async def events(self) -> AsyncIterator[dict]:
        """Yield events such as ``{"type":"audio","data":...}`` or transcript deltas."""

    @abc.abstractmethod
    async def interrupt(self) -> None: ...

    @abc.abstractmethod
    async def close(self) -> None: ...
