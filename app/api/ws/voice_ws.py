"""WebSocket handler for real-time voice sessions.

Two flavours:

* ``/ws/voice/{session_id}`` — generic browser flow. Frames contain raw PCM
  audio (binary) or JSON control messages. The server pipes audio through
  STT, drives the agent, then streams TTS audio back.

* ``/ws/voice/twilio/{session_id}`` — receives Twilio Media Streams JSON
  envelopes (mu-law @ 8k) and bridges them similarly.

Both flows share the conversational core via ``VoiceSessionManager``.
"""

from __future__ import annotations

import asyncio
import base64
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import logger
from app.voice.gateway import voice_gateway
from app.voice.providers.base import AudioChunk
from app.voice.session import voice_session_manager

router = APIRouter()


# ---------------------------------------------------------------------------
# Generic browser voice WebSocket
# ---------------------------------------------------------------------------


@router.websocket("/ws/voice/{session_id}")
async def voice_socket(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    manager = voice_session_manager()
    sess = manager.get(session_id)
    if sess is None:
        await ws.close(code=4404, reason="session_not_found")
        return

    stt = voice_gateway().stt()
    tts = voice_gateway().tts()

    audio_in: asyncio.Queue[AudioChunk] = asyncio.Queue()

    async def _audio_iter():
        while True:
            chunk = await audio_in.get()
            if chunk is None:  # type: ignore[unreachable]
                break
            yield chunk

    async def _consume_socket() -> None:
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    return
                if "bytes" in msg and msg["bytes"] is not None:
                    await audio_in.put(
                        AudioChunk(payload=msg["bytes"], sample_rate=16000, encoding="pcm16")
                    )
                elif "text" in msg and msg["text"] is not None:
                    try:
                        ctrl = json.loads(msg["text"])
                    except Exception:
                        continue
                    if ctrl.get("type") == "end":
                        return
                    if ctrl.get("type") == "text":
                        await _handle_user_text(ctrl.get("content", ""))
        except WebSocketDisconnect:
            return

    async def _handle_user_text(text: str) -> None:
        agent_text, escalation, transferred = await manager.handle_user_utterance(sess, text)
        await ws.send_json(
            {
                "type": "agent.text",
                "text": agent_text,
                "escalation": escalation.value,
                "transferred_to": transferred.value if transferred else None,
                "department": sess.department.value,
            }
        )
        # Stream TTS audio back to the client.
        try:
            async for audio in tts.stream_synthesize(agent_text, language=sess.language):
                await ws.send_bytes(audio.payload)
        except Exception as exc:
            logger.warning("TTS stream failed: {}", exc)
        await ws.send_json({"type": "agent.audio.done"})

    consumer = asyncio.create_task(_consume_socket())

    try:
        async for event in stt.stream_transcribe(_audio_iter(), language=sess.language):
            if event.get("is_final") and (text := event.get("text")):
                await ws.send_json({"type": "user.transcript", "text": text})
                await _handle_user_text(text)
            elif text := event.get("text"):
                await ws.send_json({"type": "user.partial", "text": text})
    except Exception as exc:  # pragma: no cover
        logger.exception("Voice session error: {}", exc)
        await ws.send_json({"type": "error", "error": str(exc)})
    finally:
        consumer.cancel()
        await manager.close(session_id)


# ---------------------------------------------------------------------------
# Twilio Media Streams bridge
# ---------------------------------------------------------------------------


@router.websocket("/ws/voice/twilio/{session_id}")
async def twilio_voice_socket(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    manager = voice_session_manager()
    sess = manager.get(session_id)
    if sess is None:
        await ws.close(code=4404)
        return

    logger.info("Twilio media stream connected session={}", session_id)
    try:
        while True:
            raw = await ws.receive_text()
            event = json.loads(raw)
            kind = event.get("event")
            if kind == "media":
                # Twilio sends mu-law @ 8k base64-encoded audio. Real
                # deployments transcode to PCM16/16k for Deepgram. The
                # transcoding is an extension point; we only outline it here.
                _audio = base64.b64decode(event["media"]["payload"])
                # NOTE: pipe `_audio` through a transcoder + STT and call
                # manager.handle_user_utterance() on final transcripts.
            elif kind == "stop":
                break
    except WebSocketDisconnect:
        pass
    finally:
        await manager.close(session_id)
