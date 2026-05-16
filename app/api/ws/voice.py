"""Voice WebSocket handlers.

Two endpoints are registered here:

/ws/voice/{session_id}
    Full-duplex browser voice pipeline:
    Client → raw PCM16 audio bytes (binary frames)
    Server → JSON text frames:
        {"type": "vad",        "is_speech": bool, "energy_db": float}
        {"type": "transcript", "text": str, "is_final": bool}
        {"type": "agent",      "text": str, "department": str}
        {"type": "audio",      "data": "<base64-mp3>", "provider": str}
        {"type": "error",      "message": str}
        {"type": "ping"}

/ws/voice/twilio/{session_id}
    Twilio Media Stream handler.
    Twilio sends JSON-envelope messages over the WS:
        {"event": "connected"}
        {"event": "start", "start": {...}}
        {"event": "media", "media": {"payload": "<base64-mulaw>"}}
        {"event": "stop"}
    Server responds with Twilio <Response> XML containing <Play> when TTS
    audio is ready (Twilio's media-stream approach — the WS sends back
    speech audio as base64 encoded µ-law 8 kHz).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from typing import Final

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.voice.vad import EnergyVAD, mulaw_to_pcm16
from app.voice.session import voice_session_manager
from app.services.chat_service import chat_service
from app.models.schemas import ChatRequest

router = APIRouter(tags=["voice-ws"])

# --- constants ---
_CHUNK_THRESHOLD_BYTES: Final[int] = 16_000 * 2 * 1  # ~1 s of 16 kHz PCM16
_SILENCE_FLUSH_SECS: Final[float] = 1.0               # flush after N seconds of silence


# ─────────────────────────────────────────────────────────────────────────────
# Browser full-duplex WebSocket
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/voice/{session_id}")
async def voice_websocket(ws: WebSocket, session_id: str) -> None:
    """Full-duplex voice pipeline for browser clients.

    The client sends binary PCM-16 frames (little-endian, mono, 16 kHz).
    The server streams back JSON events describing VAD state, STT transcript,
    agent reply text, and base64-encoded TTS audio.
    """
    await ws.accept()

    # Validate session exists
    session = voice_session_manager().get(session_id)
    if session is None:
        await ws.send_json({"type": "error", "message": f"Session {session_id} not found"})
        await ws.close(code=4004)
        return

    vad = EnergyVAD(sample_rate=16_000, frame_ms=20, speech_ratio_db=9.0, hangover_frames=10)
    audio_buffer: bytearray = bytearray()
    last_speech_ts: float = asyncio.get_event_loop().time()
    in_utterance: bool = False

    # Periodic ping task
    async def _ping() -> None:
        while True:
            await asyncio.sleep(15)
            try:
                await ws.send_json({"type": "ping"})
            except Exception:  # noqa: BLE001
                break

    ping_task = asyncio.create_task(_ping())

    try:
        async for raw in _iter_binary_ws(ws):
            now = asyncio.get_event_loop().time()

            # VAD
            vad_result = vad.process_pcm16_bytes(raw)
            await ws.send_json({
                "type": "vad",
                "is_speech": vad_result.is_speech,
                "energy_db": round(vad_result.energy_db, 1),
                "snr_db": round(vad_result.snr_db, 1),
            })

            if vad_result.is_speech:
                audio_buffer.extend(raw)
                last_speech_ts = now
                in_utterance = True
            elif in_utterance:
                # Append a small hangover tail
                audio_buffer.extend(raw)
                silence_secs = now - last_speech_ts
                if silence_secs >= _SILENCE_FLUSH_SECS and len(audio_buffer) > 3200:
                    # Flush utterance
                    utterance_bytes = bytes(audio_buffer)
                    audio_buffer.clear()
                    in_utterance = False
                    asyncio.create_task(
                        _process_utterance(ws, utterance_bytes, session, session_id)
                    )

            # Also flush on large buffer regardless of silence
            if len(audio_buffer) >= _CHUNK_THRESHOLD_BYTES * 4:
                utterance_bytes = bytes(audio_buffer)
                audio_buffer.clear()
                in_utterance = False
                asyncio.create_task(
                    _process_utterance(ws, utterance_bytes, session, session_id)
                )

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:  # noqa: BLE001
            pass
    finally:
        ping_task.cancel()


async def _process_utterance(
    ws: WebSocket,
    audio_bytes: bytes,
    session: object,
    session_id: str,
) -> None:
    """STT → agent → TTS pipeline for one voice utterance."""
    # 1. STT
    transcript = await _stt(audio_bytes)
    if not transcript:
        return
    await ws.send_json({"type": "transcript", "text": transcript, "is_final": True})

    # 2. Agent
    dept = getattr(session, "department", "reception")
    user_id = getattr(session, "user_id", "voice-user")
    tenant_id = getattr(session, "tenant_id", "default")
    chat_req = ChatRequest(
        message=transcript,
        department=str(dept),
        session_id=session_id,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    try:
        chat_resp = await chat_service().handle(chat_req)
        reply_text = chat_resp.message.content or ""
    except Exception as exc:  # noqa: BLE001
        reply_text = "I'm sorry, I encountered an error processing your request."
        await ws.send_json({"type": "error", "message": str(exc)})
    await ws.send_json({"type": "agent", "text": reply_text, "department": str(dept)})

    # 3. TTS
    try:
        audio_mp3, provider = await _tts(reply_text)
        b64 = base64.b64encode(audio_mp3).decode()
        await ws.send_json({"type": "audio", "data": b64, "provider": provider, "mime": "audio/mpeg"})
    except Exception as exc:  # noqa: BLE001
        await ws.send_json({"type": "error", "message": f"TTS: {exc}"})


# ─────────────────────────────────────────────────────────────────────────────
# Twilio Media Stream WebSocket
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/voice/twilio/{session_id}")
async def twilio_media_stream(ws: WebSocket, session_id: str) -> None:
    """Handle Twilio Media Stream protocol.

    Twilio streams µ-law 8 kHz audio.  We decode to PCM16, run VAD+STT,
    call the agent, synthesize speech, and send back µ-law audio chunks.
    """
    await ws.accept()

    session = voice_session_manager().get(session_id)
    if session is None:
        await ws.close(code=4004)
        return

    vad = EnergyVAD(sample_rate=8_000, frame_ms=20, speech_ratio_db=8.0, hangover_frames=12)
    audio_buffer: bytearray = bytearray()
    last_speech_ts = asyncio.get_event_loop().time()
    in_utterance = False
    stream_sid: str | None = None

    try:
        while True:
            try:
                text = await asyncio.wait_for(ws.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                continue

            msg = json.loads(text)
            event = msg.get("event", "")

            if event == "connected":
                continue

            elif event == "start":
                stream_sid = msg.get("start", {}).get("streamSid")
                # Send greeting TTS
                greeting = "Thank you for calling. I'm your AI assistant. How can I help you today?"
                asyncio.create_task(_send_twilio_tts(ws, greeting, stream_sid))

            elif event == "media":
                payload_b64 = msg.get("media", {}).get("payload", "")
                if not payload_b64:
                    continue
                mulaw_bytes = base64.b64decode(payload_b64)
                pcm16_bytes = mulaw_to_pcm16(mulaw_bytes)

                now = asyncio.get_event_loop().time()
                vad_result = vad.process_pcm16_bytes(pcm16_bytes)

                if vad_result.is_speech:
                    audio_buffer.extend(pcm16_bytes)
                    last_speech_ts = now
                    in_utterance = True
                elif in_utterance:
                    audio_buffer.extend(pcm16_bytes)
                    if (now - last_speech_ts) >= _SILENCE_FLUSH_SECS and len(audio_buffer) > 1600:
                        utterance_bytes = bytes(audio_buffer)
                        audio_buffer.clear()
                        in_utterance = False
                        asyncio.create_task(
                            _process_twilio_utterance(ws, utterance_bytes, session, session_id, stream_sid)
                        )

            elif event == "stop":
                break

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass


async def _process_twilio_utterance(
    ws: WebSocket,
    audio_bytes: bytes,
    session: object,
    session_id: str,
    stream_sid: str | None,
) -> None:
    transcript = await _stt(audio_bytes, sample_rate=8000)
    if not transcript:
        return

    dept = getattr(session, "department", "reception")
    user_id = getattr(session, "user_id", "twilio-caller")
    tenant_id = getattr(session, "tenant_id", "default")
    chat_req = ChatRequest(
        message=transcript,
        department=str(dept),
        session_id=session_id,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    try:
        chat_resp = await chat_service().handle(chat_req)
        reply_text = chat_resp.message.content or "I'm sorry, please repeat that."
    except Exception:  # noqa: BLE001
        reply_text = "I'm sorry, there was an error. Please try again."

    await _send_twilio_tts(ws, reply_text, stream_sid)


async def _send_twilio_tts(ws: WebSocket, text: str, stream_sid: str | None) -> None:
    """Synthesize text and send as Twilio media chunks."""
    try:
        audio_mp3, _ = await _tts(text)
        # Twilio Media Stream expects µ-law 8 kHz audio.
        # We encode the full MP3 blob for now (Twilio will auto-convert if given mp3).
        b64 = base64.b64encode(audio_mp3).decode()
        await ws.send_json({
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": b64},
        })
    except Exception:  # noqa: BLE001
        pass


# ─────────────────────────────────────────────────────────────────────────────
# STT / TTS helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _stt(audio_bytes: bytes, sample_rate: int = 16_000) -> str:
    """Transcribe raw PCM16 audio. Tries Deepgram first, then Whisper."""
    import aiohttp  # type: ignore

    # Convert PCM16 to WAV in-memory so providers accept it
    wav_bytes = _pcm16_to_wav(audio_bytes, sample_rate=sample_rate)

    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    if deepgram_key:
        try:
            url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"
            headers = {
                "Authorization": f"Token {deepgram_key}",
                "Content-Type": "audio/wav",
            }
            async with aiohttp.ClientSession() as s:
                async with s.post(url, headers=headers, data=wav_bytes, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status == 200:
                        body = await r.json()
                        return (
                            body.get("results", {})
                                .get("channels", [{}])[0]
                                .get("alternatives", [{}])[0]
                                .get("transcript", "")
                                .strip()
                        )
        except Exception:  # noqa: BLE001
            pass

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            form = aiohttp.FormData()
            form.add_field("model", "whisper-1")
            form.add_field("file", wav_bytes, filename="audio.wav", content_type="audio/wav")
            headers = {"Authorization": f"Bearer {openai_key}"}
            async with aiohttp.ClientSession() as s:
                async with s.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, data=form, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 200:
                        body = await r.json()
                        return (body.get("text") or "").strip()
        except Exception:  # noqa: BLE001
            pass

    return ""


async def _tts(text: str) -> tuple[bytes, str]:
    """Synthesize text. Returns (mp3_bytes, provider_name)."""
    import aiohttp  # type: ignore

    eleven_key = os.getenv("ELEVENLABS_API_KEY", "")
    if eleven_key:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": eleven_key, "Content-Type": "application/json"}
        body = {
            "text": text[:4096],
            "model_id": "eleven_turbo_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status == 200:
                        return await r.read(), "elevenlabs"
        except Exception:  # noqa: BLE001
            pass

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        url = "https://api.openai.com/v1/audio/speech"
        headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
        body = {"model": "tts-1", "input": text[:4096], "voice": "nova", "response_format": "mp3"}
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=25)) as r:
                if r.status == 200:
                    return await r.read(), "openai"
                err = await r.text()
                raise RuntimeError(f"OpenAI TTS {r.status}: {err}")

    raise RuntimeError("No TTS provider configured")


def _pcm16_to_wav(pcm16: bytes, sample_rate: int = 16_000, channels: int = 1) -> bytes:
    """Wrap raw PCM16 bytes in a minimal WAV container."""
    import struct as st

    n_samples   = len(pcm16) // 2
    byte_rate   = sample_rate * channels * 2
    block_align = channels * 2
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(st.pack("<I", 36 + len(pcm16)))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(st.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, 16))
    buf.write(b"data")
    buf.write(st.pack("<I", len(pcm16)))
    buf.write(pcm16)
    return buf.getvalue()


async def _iter_binary_ws(ws: WebSocket):
    """Yield binary frames from the WebSocket until disconnect."""
    while True:
        try:
            msg = await ws.receive()
        except WebSocketDisconnect:
            return
        if msg["type"] == "websocket.disconnect":
            return
        if msg["type"] == "websocket.receive":
            data = msg.get("bytes")
            if data:
                yield data
