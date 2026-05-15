"""Voice gateway: factory + abstraction across pluggable providers."""

from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import VoiceProviderError
from app.core.logging import logger
from app.voice.providers.base import RealtimeProvider, STTProvider, TTSProvider


class VoiceGateway:
    """Resolves voice providers by name with sensible defaults + fallbacks.

    All voice-facing services (websocket handlers, telephony, agent voice
    output) go through this gateway -- never instantiate providers directly.
    """

    def __init__(self) -> None:
        self._stt_cache: dict[str, STTProvider] = {}
        self._tts_cache: dict[str, TTSProvider] = {}
        self._rt_cache: dict[str, RealtimeProvider] = {}

    # ---- STT -----------------------------------------------------------

    def stt(self, provider: str | None = None) -> STTProvider:
        name = (provider or settings.voice_stt_provider).lower()
        if name in self._stt_cache:
            return self._stt_cache[name]

        if name == "deepgram":
            from app.voice.providers.deepgram import DeepgramSTT
            inst: STTProvider = DeepgramSTT()
        elif name == "azure":
            from app.voice.providers.azure import AzureSTT
            inst = AzureSTT()
        elif name == "google":
            from app.voice.providers.google import GoogleSTT
            inst = GoogleSTT()
        else:
            raise VoiceProviderError(f"Unknown STT provider: {name}")

        self._stt_cache[name] = inst
        return inst

    # ---- TTS -----------------------------------------------------------

    def tts(self, provider: str | None = None) -> TTSProvider:
        name = (provider or settings.voice_tts_provider).lower()
        if name in self._tts_cache:
            return self._tts_cache[name]

        if name == "elevenlabs":
            from app.voice.providers.elevenlabs import ElevenLabsTTS
            inst: TTSProvider = ElevenLabsTTS()
        elif name == "azure":
            from app.voice.providers.azure import AzureTTS
            inst = AzureTTS()
        elif name == "google":
            from app.voice.providers.google import GoogleTTS
            inst = GoogleTTS()
        else:
            raise VoiceProviderError(f"Unknown TTS provider: {name}")

        self._tts_cache[name] = inst
        return inst

    # ---- Realtime (full duplex) ---------------------------------------

    def realtime(self, provider: str | None = None) -> RealtimeProvider:
        name = (provider or settings.voice_realtime_provider).lower()
        if name in self._rt_cache:
            return self._rt_cache[name]

        if name == "openai_realtime":
            from app.voice.providers.openai_realtime import OpenAIRealtimeProvider
            inst: RealtimeProvider = OpenAIRealtimeProvider()
        elif name == "livekit":
            from app.voice.providers.livekit_provider import LiveKitProvider
            inst = LiveKitProvider()
        else:
            raise VoiceProviderError(f"Unknown realtime provider: {name}")

        self._rt_cache[name] = inst
        logger.info("Voice realtime provider resolved: {}", name)
        return inst


_gateway: VoiceGateway | None = None


def voice_gateway() -> VoiceGateway:
    global _gateway
    if _gateway is None:
        _gateway = VoiceGateway()
    return _gateway
