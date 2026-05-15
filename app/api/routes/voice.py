"""Voice REST endpoints (session bootstrap, telephony, telephony webhook)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.core.types import Department
from app.models.schemas import Principal, VoiceSessionDescriptor, VoiceSessionStartRequest
from app.security.auth import get_principal
from app.voice.gateway import voice_gateway
from app.voice.session import voice_session_manager

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/sessions", response_model=VoiceSessionDescriptor)
async def open_voice_session(
    payload: VoiceSessionStartRequest,
    principal: Principal = Depends(get_principal),
) -> VoiceSessionDescriptor:
    department = payload.department or Department.RECEPTION
    sess = await voice_session_manager().open(
        user_id=payload.user_id or principal.user_id,
        tenant_id=payload.tenant_id or principal.tenant_id,
        department=department,
        language=payload.language,
    )
    ws_url = f"/api/v1/ws/voice/{sess.session_id}"
    return VoiceSessionDescriptor(
        session_id=sess.session_id,
        department=sess.department,
        language=sess.language,
        realtime_provider=sess.realtime_provider,
        stt_provider=settings.voice_stt_provider,
        tts_provider=settings.voice_tts_provider,
        websocket_url=ws_url,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@router.delete("/sessions/{session_id}")
async def close_voice_session(
    session_id: str,
    principal: Principal = Depends(get_principal),  # noqa: ARG001
) -> dict:
    await voice_session_manager().close(session_id)
    return {"closed": True, "session_id": session_id}


# ---- Twilio inbound webhook ---------------------------------------------


@router.post("/twilio/incoming", response_class=PlainTextResponse)
async def twilio_incoming(request: Request) -> str:
    """TwiML endpoint that bridges an inbound PSTN call to our voice WS."""
    from app.voice.providers.twilio_provider import TwilioVoiceProvider

    provider = TwilioVoiceProvider()
    if not provider.is_configured():
        raise HTTPException(status_code=503, detail="Twilio not configured")

    base = str(request.base_url).rstrip("/").replace("http://", "wss://").replace(
        "https://", "wss://"
    )
    # Inbound PSTN calls are routed via the receptionist.
    sess = await voice_session_manager().open(
        user_id="phone-caller",
        tenant_id=None,
        department=Department.RECEPTION,
        language="en",
    )
    ws_url = f"{base}/api/v1/ws/voice/twilio/{sess.session_id}"
    return provider.inbound_twiml(ws_url=ws_url, greeting="Connecting you to the AI workforce.")


# ---- LiveKit join token --------------------------------------------------


@router.post("/livekit/token")
async def livekit_token(
    room: str,
    identity: str,
    principal: Principal = Depends(get_principal),  # noqa: ARG001
) -> dict:
    from app.voice.providers.livekit_provider import LiveKitProvider

    provider = LiveKitProvider()
    return {"url": provider.url, "token": provider.mint_access_token(room, identity)}
