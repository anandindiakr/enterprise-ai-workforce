"""Voice REST endpoints — session management, STT, TTS, telephony."""

from __future__ import annotations

import io
import json
import os
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.types import Department
from app.models.schemas import Principal, VoiceSessionDescriptor, VoiceSessionStartRequest
from app.security.auth import optional_principal, get_principal
from app.voice.gateway import voice_gateway
from app.voice.session import voice_session_manager

router = APIRouter(prefix="/voice", tags=["voice"])


# ── Voice Provider Configuration Status ─────────────────────────────────────

@router.get("/config")
async def voice_config() -> dict:
    """Report which voice providers are currently configured.

    This is called by the frontend to show provider status badges.
    Does NOT require authentication so the settings page can call it.
    """
    deepgram_key  = bool(os.getenv("DEEPGRAM_API_KEY") or settings.deepgram_api_key)
    eleven_key    = bool(os.getenv("ELEVENLABS_API_KEY") or settings.elevenlabs_api_key)
    openai_key    = bool(os.getenv("OPENAI_API_KEY") or settings.openai_api_key)
    twilio_sid    = bool(os.getenv("TWILIO_ACCOUNT_SID") or settings.twilio_account_sid)
    livekit_key   = bool(os.getenv("LIVEKIT_API_KEY") or settings.livekit_api_key)
    azure_key     = bool(os.getenv("AZURE_SPEECH_KEY") or settings.azure_speech_key)
    singtel_configured = bool(
        (os.getenv("SINGTEL_SIP_SERVER") or settings.singtel_sip_server)
        and (os.getenv("SINGTEL_SIP_USERNAME") or settings.singtel_sip_username)
        and (os.getenv("SINGTEL_SIP_PASSWORD") or settings.singtel_sip_password)
    )

    stt_provider  = "deepgram" if deepgram_key else ("whisper" if openai_key else None)
    tts_provider  = "elevenlabs" if eleven_key else ("openai-tts" if openai_key else None)

    return {
        "stt": {
            "active": stt_provider,
            "providers": {
                "deepgram":  {"configured": deepgram_key,  "label": "Deepgram Nova-2"},
                "whisper":   {"configured": openai_key,    "label": "OpenAI Whisper"},
                "azure":     {"configured": azure_key,     "label": "Azure Speech"},
            },
        },
        "tts": {
            "active": tts_provider,
            "providers": {
                "elevenlabs": {"configured": eleven_key,  "label": "ElevenLabs Turbo"},
                "openai-tts": {"configured": openai_key, "label": "OpenAI TTS-1"},
                "azure":      {"configured": azure_key,  "label": "Azure Speech"},
            },
        },
        "telephony": {
            "twilio":  {"configured": twilio_sid,  "label": "Twilio"},
            "livekit": {"configured": livekit_key, "label": "LiveKit"},
            "singtel": {
                "configured": singtel_configured,
                "label": "Singtel SIP (B3Networks)",
                "ddi": settings.singtel_sip_ddi or None,
                "concurrent_calls": settings.singtel_sip_concurrent_calls,
            },
        },
        "websocket_path": "/api/v1/ws/voice/{session_id}",
    }


# ── Voice Session Management ────────────────────────────────────────────────

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


# ── Speech-to-Text ──────────────────────────────────────────────────────────

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    department: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    principal: Principal = Depends(optional_principal),  # noqa: ARG001
) -> dict:
    """
    Accept a browser audio blob (webm/ogg/wav) and return the transcript.
    Uses Deepgram when DEEPGRAM_API_KEY is set, falls back to OpenAI Whisper.
    ``language`` defaults to "en" to prevent Whisper auto-detecting background audio.
    """
    audio_bytes = await audio.read()
    lang = language or "en"

    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    if deepgram_key:
        try:
            transcript = await _deepgram_stt(audio_bytes, audio.content_type or "audio/webm")
            return {"transcript": transcript, "provider": "deepgram"}
        except Exception:  # noqa: BLE001
            pass  # Fall through to Whisper

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            transcript = await _whisper_stt(audio_bytes, audio.filename or "audio.webm", language=lang)
            return {"transcript": transcript, "provider": "whisper"}
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"STT failed: {exc}") from exc

    raise HTTPException(
        status_code=503,
        detail="No STT provider configured. Set DEEPGRAM_API_KEY or OPENAI_API_KEY.",
    )


async def _deepgram_stt(audio_bytes: bytes, content_type: str) -> str:
    """Call Deepgram Nova-2 REST API."""
    import aiohttp  # type: ignore

    url = "https://api.deepgram.com/v1/listen?model=nova-2&language=en&smart_format=true"
    headers = {
        "Authorization": f"Token {os.environ['DEEPGRAM_API_KEY']}",
        "Content-Type": content_type,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=audio_bytes) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Deepgram {resp.status}: {text}")
            body = await resp.json()
    transcript = (
        body.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
    )
    return transcript.strip()


async def _whisper_stt(audio_bytes: bytes, filename: str, language: str = "en") -> str:
    """Call OpenAI Whisper via the files API.

    Pass ``language="auto"`` (or empty) to let Whisper detect the language
    automatically.  Use an ISO-639-1 code (e.g. "en", "hi", "ta") to force a
    specific language and avoid ambient-audio misdetection.
    """
    import aiohttp  # type: ignore

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}
    form = aiohttp.FormData()
    form.add_field("model", "whisper-1")
    # Only pass language when explicitly chosen — "auto" / empty = let Whisper decide.
    if language and language.lower() not in ("auto", ""):
        form.add_field("language", language)
    form.add_field("file", audio_bytes, filename=filename, content_type="audio/webm")
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=form) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Whisper {resp.status}: {text}")
            body = await resp.json()
    return (body.get("text") or "").strip()


# ── Text-to-Speech ──────────────────────────────────────────────────────────

class SpeakRequest(BaseModel):
    text: str
    department: Optional[str] = None
    voice_id: Optional[str] = None


@router.post("/speak")
async def speak_text(
    payload: SpeakRequest,
    principal: Principal = Depends(optional_principal),  # noqa: ARG001
) -> StreamingResponse:
    """
    Convert text to speech.
    Uses ElevenLabs when configured, falls back to OpenAI TTS.
    Returns the raw audio stream (audio/mpeg).
    """
    eleven_key = os.getenv("ELEVENLABS_API_KEY", "")
    if eleven_key:
        try:
            audio_bytes = await _elevenlabs_tts(
                text=payload.text,
                voice_id=payload.voice_id or os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL"),
            )
            return StreamingResponse(
                io.BytesIO(audio_bytes),
                media_type="audio/mpeg",
                headers={"Content-Disposition": "inline; filename=speech.mp3"},
            )
        except Exception:  # noqa: BLE001
            pass  # Fall through to OpenAI

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            audio_bytes = await _openai_tts(payload.text)
            return StreamingResponse(
                io.BytesIO(audio_bytes),
                media_type="audio/mpeg",
                headers={"Content-Disposition": "inline; filename=speech.mp3"},
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"TTS failed: {exc}") from exc

    raise HTTPException(
        status_code=503,
        detail="No TTS provider configured. Set ELEVENLABS_API_KEY or OPENAI_API_KEY.",
    )


async def _elevenlabs_tts(text: str, voice_id: str) -> bytes:
    import aiohttp  # type: ignore

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
        "Content-Type": "application/json",
    }
    body = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": 0.9},
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, headers=headers) as resp:
            if resp.status != 200:
                err = await resp.text()
                raise RuntimeError(f"ElevenLabs {resp.status}: {err}")
            return await resp.read()


async def _openai_tts(text: str) -> bytes:
    import aiohttp  # type: ignore

    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }
    body = {"model": "tts-1", "input": text, "voice": "nova", "response_format": "mp3", "speed": 0.9}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, headers=headers) as resp:
            if resp.status != 200:
                err = await resp.text()
                raise RuntimeError(f"OpenAI TTS {resp.status}: {err}")
            return await resp.read()


# ── Twilio inbound webhook ──────────────────────────────────────────────────

@router.post("/twilio/incoming", response_class=PlainTextResponse)
async def twilio_incoming(request: Request) -> str:
    from app.voice.providers.twilio_provider import TwilioVoiceProvider

    provider = TwilioVoiceProvider()
    if not provider.is_configured():
        raise HTTPException(status_code=503, detail="Twilio not configured")

    base = str(request.base_url).rstrip("/").replace("http://", "wss://").replace("https://", "wss://")
    sess = await voice_session_manager().open(
        user_id="phone-caller",
        tenant_id=None,
        department=Department.RECEPTION,
        language="en",
    )
    ws_url = f"{base}/api/v1/ws/voice/twilio/{sess.session_id}"
    return provider.inbound_twiml(ws_url=ws_url, greeting="Connecting you to the AI workforce.")


# ── LiveKit join token ──────────────────────────────────────────────────────

@router.post("/livekit/token")
async def livekit_token(
    room: str,
    identity: str,
    principal: Principal = Depends(get_principal),  # noqa: ARG001
) -> dict:
    from app.voice.providers.livekit_provider import LiveKitProvider

    provider = LiveKitProvider()
    return {"url": provider.url, "token": provider.mint_access_token(room, identity)}


# ── Streaming TTS ────────────────────────────────────────────────────────────

@router.post("/speak/stream")
async def speak_stream(
    payload: SpeakRequest,
    principal: Principal = Depends(optional_principal),  # noqa: ARG001
) -> StreamingResponse:
    """
    Streaming TTS endpoint.
    Returns raw audio bytes in chunks via chunked transfer encoding.
    Uses ElevenLabs streaming when configured, falls back to full OpenAI TTS.
    """
    eleven_key = os.getenv("ELEVENLABS_API_KEY", "")
    if eleven_key:
        async def _eleven_stream() -> AsyncIterator[bytes]:
            import aiohttp  # type: ignore
            voice_id = payload.voice_id or os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
            headers = {
                "xi-api-key": eleven_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            }
            body = {
                "text": payload.text[:4096],
                "model_id": "eleven_turbo_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": 0.9},
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=body, headers=headers) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        raise RuntimeError(f"ElevenLabs {resp.status}: {err}")
                    async for chunk in resp.content.iter_chunked(4096):
                        yield chunk

        return StreamingResponse(
            _eleven_stream(),
            media_type="audio/mpeg",
            headers={"X-TTS-Provider": "elevenlabs", "X-Accel-Buffering": "no"},
        )

    # Fallback: full OpenAI TTS
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        audio_bytes = await _openai_tts(payload.text)
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"X-TTS-Provider": "openai"},
        )

    raise HTTPException(
        status_code=503,
        detail="No TTS provider configured. Set ELEVENLABS_API_KEY or OPENAI_API_KEY.",
    )
