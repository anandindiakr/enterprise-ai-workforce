"""WebSocket handlers for real-time voice.

Two endpoints:

/ws/voice/{session_id}
    Full-duplex browser voice pipeline:
    - Client sends binary PCM-16 (mono, 16 kHz) frames
    - Server emits JSON events:
        {"type": "vad",        "is_speech": bool, "energy_db": float, "snr_db": float}
        {"type": "transcript", "text": str, "is_final": bool}
        {"type": "agent",      "text": str, "department": str}
        {"type": "audio",      "data": "<base64-mp3>", "provider": str, "mime": "audio/mpeg"}
        {"type": "error",      "message": str}
        {"type": "ping"}
    - Client may also send JSON: {"type": "text", "content": "<text>"}
      to inject a manual utterance without audio

/ws/voice/twilio/{session_id}
    Twilio Media Streams bridge (µ-law 8 kHz ↔ PCM16).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import struct
from typing import Final

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import logger
from app.core.exceptions import AuthenticationError
from app.security.auth import decode_token
from app.voice.vad import EnergyVAD, mulaw_to_pcm16
from app.voice.session import voice_session_manager, _strip_control_signals
from app.models.schemas import ChatRequest
from app.services.chat_service import chat_service

router = APIRouter()

_SILENCE_FLUSH_SECS: Final[float] = 1.0
_MAX_BUFFER_BYTES:   Final[int]   = 16_000 * 2 * 8  # 8 s PCM16 @ 16 kHz


# ─────────────────────────────────────────────────────────────────────────────
# Browser full-duplex WebSocket
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/voice/{session_id}")
async def voice_socket(ws: WebSocket, session_id: str) -> None:
    # ── JWT auth via ?token= query param ──────────────────────────────────
    token = ws.query_params.get("token")
    if token:
        try:
            decode_token(token)
        except AuthenticationError as exc:
            await ws.close(code=4001)
            logger.warning("Voice WS auth rejected session={}: {}", session_id, exc)
            return
    # Allow unauthenticated connections in dev/staging (token optional);
    # set REQUIRE_WS_AUTH=true in production to harden.
    import os
    if not token and os.getenv("REQUIRE_WS_AUTH", "").lower() == "true":
        await ws.close(code=4001)
        return

    await ws.accept()

    manager = voice_session_manager()
    session = manager.get(session_id)
    if session is None:
        # Auto-create an on-demand voice session so the frontend doesn't need
        # to call POST /voice/sessions first.
        try:
            from app.core.types import Department
            dept_param = ws.query_params.get("department", "reception")
            user_id    = ws.query_params.get("user_id", "anonymous")
            tenant_id  = ws.query_params.get("tenant_id", "default")
            try:
                dept_enum = Department(dept_param)
            except ValueError:
                dept_enum = Department.RECEPTION
            session = await manager.open(
                user_id=user_id,
                tenant_id=tenant_id,
                department=dept_enum,
            )
            # The manager assigns its own session_id; keep it consistent
            session_id = session.session_id
        except Exception as exc:  # noqa: BLE001
            await ws.send_json({"type": "error", "message": f"Could not create session: {exc}"})
            await ws.close(code=4004)
            return

    vad = EnergyVAD(sample_rate=16_000, frame_ms=20, speech_ratio_db=9.0, hangover_frames=10)
    audio_buffer: bytearray = bytearray()
    last_speech_ts: float = asyncio.get_event_loop().time()
    in_utterance: bool = False

    async def _ping() -> None:
        while True:
            await asyncio.sleep(15)
            try:
                await ws.send_json({"type": "ping"})
            except Exception:  # noqa: BLE001
                break

    ping_task = asyncio.create_task(_ping())

    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive(), timeout=60)
            except asyncio.TimeoutError:
                continue

            if msg.get("type") == "websocket.disconnect":
                break

            # ── Text control frame ─────────────────────────────────────────
            if msg.get("text"):
                try:
                    ctrl = json.loads(msg["text"])
                    if ctrl.get("type") == "text":
                        text = ctrl.get("content", "").strip()
                        if text:
                            asyncio.create_task(
                                _process_utterance(ws, None, text, session, session_id)
                            )
                except Exception:  # noqa: BLE001
                    pass
                continue

            # ── Binary audio frame ─────────────────────────────────────────
            raw: bytes | None = msg.get("bytes")
            if not raw:
                continue

            now = asyncio.get_event_loop().time()
            vad_result = vad.process_pcm16_bytes(raw)
            await ws.send_json({
                "type":      "vad",
                "is_speech": vad_result.is_speech,
                "energy_db": round(vad_result.energy_db, 1),
                "snr_db":    round(vad_result.snr_db, 1),
            })

            if vad_result.is_speech:
                audio_buffer.extend(raw)
                last_speech_ts = now
                in_utterance = True
            elif in_utterance:
                audio_buffer.extend(raw)
                silence_secs = now - last_speech_ts
                if silence_secs >= _SILENCE_FLUSH_SECS and len(audio_buffer) > 3200:
                    utterance = bytes(audio_buffer)
                    audio_buffer.clear()
                    in_utterance = False
                    asyncio.create_task(
                        _process_utterance(ws, utterance, None, session, session_id)
                    )

            # Safety: flush oversized buffer
            if len(audio_buffer) >= _MAX_BUFFER_BYTES:
                utterance = bytes(audio_buffer)
                audio_buffer.clear()
                in_utterance = False
                asyncio.create_task(
                    _process_utterance(ws, utterance, None, session, session_id)
                )

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.exception("Voice WS error session={}: {}", session_id, exc)
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:  # noqa: BLE001
            pass
    finally:
        ping_task.cancel()
        logger.info("Voice WS closed session={}", session_id)


# ─────────────────────────────────────────────────────────────────────────────
# Twilio Media Stream WebSocket
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/voice/twilio/{session_id}")
async def twilio_voice_socket(ws: WebSocket, session_id: str) -> None:
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

    logger.info("Twilio media stream connected session={}", session_id)

    try:
        while True:
            try:
                raw_text = await asyncio.wait_for(ws.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break

            event = json.loads(raw_text)
            kind  = event.get("event", "")

            if kind == "connected":
                continue

            elif kind == "start":
                stream_sid = event.get("start", {}).get("streamSid")
                greeting = (
                    "Thank you for calling. This is your AI assistant. How can I help you today?"
                )
                asyncio.create_task(_send_twilio_tts(ws, greeting, stream_sid))

            elif kind == "media":
                payload_b64 = event.get("media", {}).get("payload", "")
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
                        utterance = bytes(audio_buffer)
                        audio_buffer.clear()
                        in_utterance = False
                        asyncio.create_task(
                            _process_twilio_utterance(ws, utterance, session, session_id, stream_sid)
                        )

            elif kind == "stop":
                break

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.exception("Twilio WS error session={}: {}", session_id, exc)
    finally:
        await voice_session_manager().close(session_id)
        logger.info("Twilio WS closed session={}", session_id)


# ─────────────────────────────────────────────────────────────────────────────
# Shared pipeline helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _process_utterance(
    ws: WebSocket,
    audio_bytes: bytes | None,
    text_override: str | None,
    session: object,
    session_id: str,
) -> None:
    """STT → agent → TTS for one browser utterance."""
    # 1. STT (skip if text already provided)
    if text_override:
        transcript = text_override
    else:
        transcript = await _stt(audio_bytes or b"")
    if not transcript:
        return

    await ws.send_json({"type": "transcript", "text": transcript, "is_final": True})

    # 2. Agent
    # NOTE: Department is a (str, Enum); str(Department.RECEPTION) -> "Department.RECEPTION".
    # We must use .value ("reception") so ChatRequest enum validation passes.
    _dept_raw = getattr(session, "department", "reception")
    dept      = _dept_raw.value if hasattr(_dept_raw, "value") else str(_dept_raw)
    user_id   = str(getattr(session, "user_id",   "voice-user"))
    tenant_id = str(getattr(session, "tenant_id", "default"))

    async def _emit(text: str, dept_for_voice: str, *, strip: bool = True) -> None:
        """Send an agent message + its TTS audio to the client.

        `strip` removes control-signal / prose-transfer leaks from LLM output.
        Set strip=False for trusted fixed phrases (e.g. the handoff line, which
        otherwise trips the prose-transfer filter).
        """
        if strip:
            text = _strip_control_signals(text)
        text = (text or "").strip() or "I'm here to help. How can I assist you?"
        await ws.send_json({"type": "agent", "text": text, "department": dept_for_voice})
        try:
            audio_mp3, provider = await _tts(text)
            await ws.send_json({
                "type":     "audio",
                "data":     base64.b64encode(audio_mp3).decode(),
                "provider": provider,
                "mime":     "audio/mpeg",
            })
        except Exception as exc:  # noqa: BLE001
            await ws.send_json({"type": "error", "message": f"TTS: {exc}"})

    dept_labels = {
        "reception": "Reception", "customer_care": "Customer Care",
        "sales": "Sales", "hr": "HR", "finance": "Finance",
        "technology": "Technology", "marketing": "Marketing",
    }

    try:
        chat_resp = await chat_service().handle(
            ChatRequest(
                message=transcript,
                department=dept,
                session_id=session_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        )
        reply_text = chat_resp.message.content or ""

        # --- Department transfer: hand off, switch, then let the new dept speak --
        if chat_resp.transferred_to:
            new_dept = chat_resp.transferred_to
            dept_name = new_dept.value if hasattr(new_dept, "value") else str(new_dept)
            try:
                from app.core.types import Department as _Dept
                session.department = _Dept(dept_name)  # type: ignore[attr-defined]
            except Exception:
                pass
            await ws.send_json({"type": "transfer", "department": dept_name})
            label = dept_labels.get(dept_name, dept_name.replace("_", " ").title())

            # 1) Spoken handoff from the current agent.
            await _emit(f"I'm connecting you to our {label} team now. One moment please.", dept, strip=False)

            # 2) New department picks up the SAME request and responds out loud,
            #    carrying the conversation context (same session_id).
            try:
                followup = await chat_service().handle(
                    ChatRequest(
                        message=transcript,
                        department=dept_name,
                        session_id=session_id,
                        user_id=user_id,
                        tenant_id=tenant_id,
                    )
                )
                new_reply = followup.message.content or ""
            except Exception:  # noqa: BLE001
                new_reply = ""
            if not new_reply.strip():
                new_reply = f"Hi, this is {label}. How can I help you?"
            await _emit(new_reply, dept_name)
            return

        await _emit(reply_text, dept)

    except Exception as exc:  # noqa: BLE001
        await ws.send_json({"type": "error", "message": str(exc)})
        await _emit("I'm sorry, I encountered an error. Please try again.", dept)


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

    _dept_raw = getattr(session, "department", "reception")
    dept      = _dept_raw.value if hasattr(_dept_raw, "value") else str(_dept_raw)
    user_id   = str(getattr(session, "user_id",   "twilio-caller"))
    tenant_id = str(getattr(session, "tenant_id", "default"))
    try:
        chat_resp = await chat_service().handle(
            ChatRequest(
                message=transcript,
                department=dept,
                session_id=session_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        )
        reply = chat_resp.message.content or "I'm sorry, please repeat that."
    except Exception:  # noqa: BLE001
        reply = "I'm sorry, there was an error. Please try again."

    await _send_twilio_tts(ws, reply, stream_sid)


async def _send_twilio_tts(ws: WebSocket, text: str, stream_sid: str | None) -> None:
    try:
        audio_mp3, _ = await _tts(text)
        b64 = base64.b64encode(audio_mp3).decode()
        await ws.send_json({
            "event":     "media",
            "streamSid": stream_sid,
            "media":     {"payload": b64},
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning("Twilio TTS failed: {}", exc)


# ─────────────────────────────────────────────────────────────────────────────
# STT / TTS helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _stt(audio_bytes: bytes, sample_rate: int = 16_000) -> str:
    """Transcribe raw PCM-16 audio. Tries Deepgram, then OpenAI Whisper."""
    import aiohttp  # type: ignore

    if len(audio_bytes) < 3200:
        return ""

    wav_bytes = _pcm16_to_wav(audio_bytes, sample_rate=sample_rate)

    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    if deepgram_key:
        try:
            url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&punctuate=true"
            headers = {
                "Authorization": f"Token {deepgram_key}",
                "Content-Type": "audio/wav",
            }
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    url, headers=headers, data=wav_bytes,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        body = await resp.json()
                        text = (
                            body.get("results", {})
                                .get("channels", [{}])[0]
                                .get("alternatives", [{}])[0]
                                .get("transcript", "")
                                .strip()
                        )
                        if text:
                            logger.debug("Deepgram transcript: {!r}", text)
                            return text
        except Exception as exc:  # noqa: BLE001
            logger.warning("Deepgram STT failed: {}", exc)

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            form = aiohttp.FormData()
            form.add_field("model", "whisper-1")
            form.add_field(
                "file", wav_bytes,
                filename="audio.wav",
                content_type="audio/wav",
            )
            headers = {"Authorization": f"Bearer {openai_key}"}
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers, data=form,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        body = await resp.json()
                        text = (body.get("text") or "").strip()
                        if text:
                            logger.debug("Whisper transcript: {!r}", text)
                            return text
        except Exception as exc:  # noqa: BLE001
            logger.warning("Whisper STT failed: {}", exc)

    return ""


async def _tts(text: str) -> tuple[bytes, str]:
    """Synthesize speech. ElevenLabs → OpenAI TTS fallback."""
    import aiohttp  # type: ignore

    eleven_key = os.getenv("ELEVENLABS_API_KEY", "")
    if eleven_key:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
        url      = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers  = {"xi-api-key": eleven_key, "Content-Type": "application/json"}
        payload  = {
            "text":     text[:4096],
            "model_id": "eleven_turbo_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    url, json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status == 200:
                        return await resp.read(), "elevenlabs"
        except Exception as exc:  # noqa: BLE001
            logger.warning("ElevenLabs TTS failed: {}", exc)

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        url     = "https://api.openai.com/v1/audio/speech"
        headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
        payload = {"model": "tts-1", "input": text[:4096], "voice": "nova", "response_format": "mp3"}
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status == 200:
                    return await resp.read(), "openai"
                err = await resp.text()
                raise RuntimeError(f"OpenAI TTS {resp.status}: {err}")

    raise RuntimeError("No TTS provider configured. Set ELEVENLABS_API_KEY or OPENAI_API_KEY.")


def _pcm16_to_wav(pcm16: bytes, sample_rate: int = 16_000, channels: int = 1) -> bytes:
    """Wrap raw PCM-16 little-endian bytes in a WAV container."""
    byte_rate   = sample_rate * channels * 2
    block_align = channels * 2
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(pcm16)))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", len(pcm16)))
    buf.write(pcm16)
    return buf.getvalue()
