"""LiveKit Agents adapter (room-based realtime media plane).

LiveKit gives you scalable WebRTC infrastructure; pair it with the
`livekit-agents` runtime (or your own pipeline) to expose Workforce agents
to browsers, mobile clients, and SIP gateways.
"""

from __future__ import annotations

from typing import AsyncIterator

from app.core.config import settings
from app.core.exceptions import VoiceProviderError
from app.voice.providers.base import AudioChunk, RealtimeProvider, RealtimeSession


class LiveKitProvider(RealtimeProvider):
    """Provisions LiveKit access tokens and rooms for a voice session.

    The actual media handling is performed by a LiveKit Agents worker
    process that joins the room. This adapter is responsible for
    provisioning credentials and exposing the LiveKit URL to the client.
    """

    name = "livekit"

    def __init__(self) -> None:
        self.url = settings.livekit_url
        self.api_key = settings.livekit_api_key
        self.api_secret = settings.livekit_api_secret

    def is_configured(self) -> bool:
        return bool(self.url and self.api_key and self.api_secret)

    def mint_access_token(self, room: str, identity: str, *, ttl_seconds: int = 3600) -> str:
        if not self.is_configured():
            raise VoiceProviderError("LiveKit not configured")
        try:
            from livekit import api  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise VoiceProviderError(f"livekit-api unavailable: {exc}") from exc

        token = (
            api.AccessToken(self.api_key, self.api_secret)
            .with_identity(identity)
            .with_name(identity)
            .with_grants(api.VideoGrants(room_join=True, room=room))
            .with_ttl(ttl_seconds)
        )
        return token.to_jwt()

    async def open_session(
        self,
        *,
        system_prompt: str,
        voice_id: str | None = None,
        language: str = "en",
    ) -> RealtimeSession:
        raise VoiceProviderError(
            "LiveKitProvider hands media to a livekit-agents worker; "
            "use mint_access_token() and join the room from the client."
        )


class _NullSession(RealtimeSession):  # pragma: no cover - placeholder
    async def send_audio(self, chunk: AudioChunk) -> None: ...
    async def send_text(self, text: str) -> None: ...
    async def events(self) -> AsyncIterator[dict]:
        if False:
            yield {}
    async def interrupt(self) -> None: ...
    async def close(self) -> None: ...
