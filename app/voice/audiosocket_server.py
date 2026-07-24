"""AudioSocket TCP bridge for SIP telephony (Singtel / B3Networks trunk).

Unlike Twilio, Singtel/B3Networks is a raw SIP trunk with no REST/webhook
abstraction. To bridge PSTN calls into the same STT -> Agent -> TTS pipeline
used by the browser and Twilio voice paths, an Asterisk instance registers to
the trunk (see ``deploy/asterisk/``) and, on each inbound call, connects to
this TCP server using Asterisk's ``AudioSocket()`` dialplan application. That
application speaks a small binary framed protocol carrying raw 16-bit signed
linear PCM audio at 8 kHz mono ("slin8k") -- no telephony SDK is required on
our side.

Wire format (each frame): ``1 byte kind | 2 bytes big-endian length | payload``

Kinds:
    0x00 HANGUP  -- call ended, no payload
    0x01 UUID    -- 16-byte call UUID, sent once when the connection opens
    0x10 AUDIO   -- raw slin8k PCM16 payload (both directions)
    0x03 ERROR   -- 1-byte error code payload

This module is intentionally dependency-light: it reuses the exact same
``_stt`` / ``_tts`` helpers as ``app.api.ws.voice_ws`` so STT/TTS provider
behavior (Deepgram/Whisper, ElevenLabs/OpenAI) stays identical across the
browser, Twilio, and Singtel voice paths.
"""

from __future__ import annotations

import asyncio
import io
import struct
import uuid as uuid_mod
from typing import Final

from app.core.config import settings
from app.core.logging import logger
from app.core.types import Department
from app.models.schemas import ChatRequest
from app.services.chat_service import chat_service
from app.voice.session import voice_session_manager
from app.voice.vad import EnergyVAD

KIND_HANGUP: Final[int] = 0x00
KIND_UUID:   Final[int] = 0x01
KIND_ERROR:  Final[int] = 0x03
KIND_AUDIO:  Final[int] = 0x10

_SILENCE_FLUSH_SECS: Final[float] = 1.0
_MAX_BUFFER_BYTES:   Final[int]   = 8_000 * 2 * 8  # 8 s of slin8k PCM16
_FRAME_BYTES:        Final[int]   = 320             # 20 ms @ 8 kHz * 2 bytes
_GREETING = (
    "Thank you for calling AI Algo, how can I assist you?"
)
_HOLD_PHRASE = "One moment, connecting you now."


async def _read_frame(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    header = await reader.readexactly(3)
    kind = header[0]
    length = struct.unpack(">H", header[1:3])[0]
    payload = await reader.readexactly(length) if length else b""
    return kind, payload


async def _write_frame(writer: asyncio.StreamWriter, kind: int, payload: bytes = b"") -> None:
    if writer.is_closing():
        raise ConnectionResetError("AudioSocket transport is closing")
    writer.write(bytes([kind]) + struct.pack(">H", len(payload)) + payload)
    await writer.drain()


async def _play_text(writer: asyncio.StreamWriter, text: str) -> None:
    """Synthesize `text` via the shared TTS chain and stream it back as slin8k."""
    from app.api.ws.voice_ws import _tts  # local import avoids circular import at module load

    if writer.is_closing():
        return

    try:
        audio_bytes, provider = await _tts(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("AudioSocket TTS failed: {}", exc)
        return

    try:
        pcm = _decode_to_slin8k(audio_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("AudioSocket audio decode failed (provider={}): {}", provider, exc)
        return

    for i in range(0, len(pcm), _FRAME_BYTES):
        if writer.is_closing():
            return
        chunk = pcm[i : i + _FRAME_BYTES]
        if len(chunk) < _FRAME_BYTES:
            chunk = chunk + b"\x00" * (_FRAME_BYTES - len(chunk))
        try:
            await _write_frame(writer, KIND_AUDIO, chunk)
        except (ConnectionResetError, BrokenPipeError):
            return
        await asyncio.sleep(0.02)  # real-time pacing so Asterisk's jitter buffer doesn't overrun


def _decode_to_slin8k(audio_bytes: bytes) -> bytes:
    """Decode a TTS MP3 (or WAV) payload to raw mono PCM16 @ 8 kHz."""
    import numpy as np
    import soundfile as sf

    data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 8_000 and len(data) > 1:
        data = _resample(data, sr, 8_000)
    pcm16 = np.clip(data * 32767.0, -32768, 32767).astype("<i2")
    return pcm16.tobytes()


def _resample(data, sr: int, target_sr: int):
    """Resample ``data`` from ``sr`` to ``target_sr``.

    Prefers ``scipy.signal.resample_poly`` (polyphase filter — proper
    band-limited resampling, no aliasing/noise) and falls back to plain
    linear interpolation if scipy isn't installed. The previous linear-only
    approach introduced audible noise/artifacts on the phone line.
    """
    import math

    import numpy as np

    try:
        from scipy.signal import resample_poly

        g = math.gcd(sr, target_sr)
        up, down = target_sr // g, sr // g
        return resample_poly(data, up, down).astype("float32")
    except ImportError:
        duration = len(data) / sr
        target_len = max(int(duration * target_sr), 1)
        x_old = np.linspace(0.0, duration, num=len(data), endpoint=False)
        x_new = np.linspace(0.0, duration, num=target_len, endpoint=False)
        return np.interp(x_new, x_old, data)


async def _get_branding(tenant_id: str = "default"):
    """Fetch (cached) company branding so voice scripts reflect Settings UI edits."""
    from app.core.company import get_company_branding

    try:
        return await get_company_branding(tenant_id)
    except Exception:  # noqa: BLE001
        return None


def _dept_override(branding, department: str) -> dict:
    if branding is None:
        return {}
    return (branding.agent_overrides or {}).get(department) or {}


def _company_greeting(branding, department: str = "reception") -> str:
    """Resolve the opening greeting for `department`, preferring the admin's
    configured script (Settings -> Call Scripts) over the hardcoded default."""
    override = _dept_override(branding, department)
    custom = (override.get("greeting") or override.get("script") or "").strip()
    if custom:
        company_name = (branding.company_name if branding else None) or settings.company_name
        try:
            return custom.format(company_name=company_name, department=department)
        except (KeyError, IndexError):
            return custom
    return _GREETING


def _company_transfer_message(branding, department: str) -> str:
    """Resolve the phrase spoken while transferring OUT of `department`."""
    override = _dept_override(branding, department)
    custom = (override.get("transfer_message") or "").strip()
    return custom or _HOLD_PHRASE


def _company_dept_intro(branding, department: str) -> str:
    """Resolve the greeting spoken by the NEW department right after a transfer."""
    override = _dept_override(branding, department)
    custom = (override.get("greeting") or override.get("script") or "").strip()
    if custom:
        company_name = (branding.company_name if branding else None) or settings.company_name
        try:
            return custom.format(company_name=company_name, department=department)
        except (KeyError, IndexError):
            return custom
    return _DEPT_INTROS.get(department, f"Hi, this is {_DEPT_LABELS.get(department, department.replace('_', ' ').title())}. How can I help you?")


async def _play_greeting(writer: asyncio.StreamWriter, lock: asyncio.Lock, tenant_id: str = "default") -> None:
    branding = await _get_branding(tenant_id)
    greeting = _company_greeting(branding, "reception")
    async with lock:
        await _play_text(writer, greeting)


_DEPT_LABELS = {
    "reception": "Reception", "customer_care": "Customer Care",
    "sales": "Sales", "hr": "Human Resources", "finance": "Finance",
    "technology": "Technology", "marketing": "Marketing",
}

_DEPT_INTROS = {
    "reception":      "Hi, this is Reception. How can I help you?",
    "customer_care":  "Hi there! I'm from Customer Care. I'm here to resolve your issue.",
    "sales":          "Hi! I'm your Sales agent. I can help with pricing, products, and purchases.",
    "hr":             "Hello! I'm the HR agent. I can assist with employment and HR queries.",
    "finance":        "Hi, this is Finance. I can help with billing, invoices, and payments.",
    "technology":     "Hello! This is Tech Support. I'm here to help with your technical issue.",
    "marketing":      "Hi! I'm the Marketing agent. I can help with campaigns and branding.",
}


async def _process_utterance(
    writer: asyncio.StreamWriter,
    audio_bytes: bytes,
    session: object,
    session_id: str,
    lock: asyncio.Lock,
) -> None:
    from app.api.ws.voice_ws import _stt  # local import avoids circular import at module load

    transcript = await _stt(audio_bytes, sample_rate=8_000)
    if not transcript or writer.is_closing():
        return

    dept_raw  = getattr(session, "department", "reception")
    dept      = dept_raw.value if hasattr(dept_raw, "value") else str(dept_raw)
    user_id   = str(getattr(session, "user_id", "sip-caller"))
    tenant_id = str(getattr(session, "tenant_id", "default"))

    try:
        # handle_fast() is a low-latency single-turn path (~1-2s) purpose-built
        # for voice; the full handle() multi-agent director loop takes 10-20s+
        # per turn (huge system prompts + 2 sequential LLM calls), which is
        # unusable on a live phone call and was causing long dead-air gaps.
        chat_resp = await chat_service().handle_fast(
            ChatRequest(
                message=transcript,
                department=dept,
                session_id=session_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("AudioSocket chat handling failed: {}", exc)
        if writer.is_closing():
            return
        async with lock:
            await _play_text(writer, "I'm sorry, there was an error. Please try again.")
        return

    if writer.is_closing():
        return

    # --- Department transfer: hand off, switch department on the live
    # session, then let the new department speak -- mirrors the browser
    # voice path (voice_ws.py). Without this the call previously just hung
    # after a transfer request because nothing was ever spoken/switched.
    if chat_resp.transferred_to:
        new_dept_raw = chat_resp.transferred_to
        new_dept = new_dept_raw.value if hasattr(new_dept_raw, "value") else str(new_dept_raw)
        try:
            session.department = Department(new_dept)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass

        branding = await _get_branding(tenant_id)
        # Prefer the admin's configured transfer phrase (Settings -> Call
        # Scripts) over raw LLM output -- the model can otherwise ad-lib or
        # go silent here, which is what caused dead air / made-up chatter
        # during a transfer on live calls.
        handoff = _company_transfer_message(branding, dept)

        async with lock:
            if writer.is_closing():
                return
            # Speak immediately so there's never dead air while the transfer
            # + follow-up LLM call are being prepared (previously the caller
            # heard a few seconds of silence here).
            await _play_text(writer, handoff)
            if writer.is_closing():
                return
            await _play_text(writer, _company_dept_intro(branding, new_dept))

        # Don't reuse the caller's original utterance (e.g. "transfer me to
        # sales") as a question for the new department -- that caused the
        # new agent to respond to the transfer request itself instead of
        # naturally waiting for the caller's real question, and made it
        # sound like a repeated/garbled greeting. Just let the dept intro
        # above stand and wait for the caller's next utterance.
        return

    reply = chat_resp.message.content or "I'm sorry, could you repeat that?"

    # Serialize TTS playback per-call: if two utterances get processed
    # concurrently (e.g. STT/LLM finished out of order), writing both to the
    # same TCP transport at once interleaves audio frames and sounds garbled.
    async with lock:
        if writer.is_closing():
            return
        await _play_text(writer, reply)


async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    logger.info("AudioSocket connection opened peer={}", peer)

    session = None
    session_id: str | None = None
    vad = EnergyVAD(sample_rate=8_000, frame_ms=20, speech_ratio_db=8.0, hangover_frames=12)
    audio_buffer = bytearray()
    last_speech_ts = asyncio.get_event_loop().time()
    in_utterance = False

    # A single lock per call serializes all TTS playback (greeting + every
    # utterance reply) so concurrent tasks can never write interleaved audio
    # frames to the same TCP transport at once (was causing garbled audio).
    playback_lock = asyncio.Lock()
    background_tasks: set[asyncio.Task] = set()

    def _spawn(coro) -> None:
        task = asyncio.create_task(coro)
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    try:
        while True:
            try:
                kind, payload = await _read_frame(reader)
            except (asyncio.IncompleteReadError, ConnectionResetError):
                break

            if kind == KIND_HANGUP:
                break

            elif kind == KIND_UUID:
                call_uuid = str(uuid_mod.UUID(bytes=payload)) if len(payload) == 16 else "unknown"
                logger.info("AudioSocket call UUID={}", call_uuid)
                try:
                    session = await voice_session_manager().open(
                        user_id=f"sip-{call_uuid[:8]}",
                        tenant_id="default",
                        department=Department.RECEPTION,
                    )
                    session_id = session.session_id
                    _spawn(_play_greeting(writer, playback_lock))
                except Exception as exc:  # noqa: BLE001
                    logger.exception("AudioSocket session open failed: {}", exc)
                    break

            elif kind == KIND_AUDIO:
                if session is None:
                    continue
                now = asyncio.get_event_loop().time()
                vad_result = vad.process_pcm16_bytes(payload)

                if vad_result.is_speech:
                    audio_buffer.extend(payload)
                    last_speech_ts = now
                    in_utterance = True
                elif in_utterance:
                    audio_buffer.extend(payload)
                    if (now - last_speech_ts) >= _SILENCE_FLUSH_SECS and len(audio_buffer) > 1600:
                        utterance = bytes(audio_buffer)
                        audio_buffer.clear()
                        in_utterance = False
                        _spawn(
                            _process_utterance(writer, utterance, session, session_id, playback_lock)
                        )

                if len(audio_buffer) >= _MAX_BUFFER_BYTES:
                    utterance = bytes(audio_buffer)
                    audio_buffer.clear()
                    in_utterance = False
                    _spawn(
                        _process_utterance(writer, utterance, session, session_id, playback_lock)
                    )

            elif kind == KIND_ERROR:
                logger.warning("AudioSocket ERROR frame received, code={}", payload)

    except Exception as exc:  # noqa: BLE001
        logger.exception("AudioSocket connection error peer={}: {}", peer, exc)
    finally:
        # Cancel any in-flight STT/LLM/TTS tasks before closing the socket --
        # without this, a task still running after hangup would eventually
        # try to write audio frames to an already-closed transport and raise
        # an unhandled "Task exception was never retrieved" RuntimeError.
        for task in list(background_tasks):
            task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)

        if session_id:
            try:
                await voice_session_manager().close(session_id)
            except Exception:  # noqa: BLE001
                pass
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        logger.info("AudioSocket connection closed peer={}", peer)


async def start_audiosocket_server() -> asyncio.base_events.Server:
    """Start the AudioSocket TCP listener. Call once during app startup."""
    server = await asyncio.start_server(
        handle_connection,
        host=settings.audiosocket_host,
        port=settings.audiosocket_port,
    )
    logger.info(
        "AudioSocket server listening on {}:{}",
        settings.audiosocket_host, settings.audiosocket_port,
    )
    return server
