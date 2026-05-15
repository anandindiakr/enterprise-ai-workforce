"""Real-time voice session lifecycle and state machine.

A :class:`VoiceSession` couples:
  * a realtime provider session (or STT + TTS pipeline)
  * a Workforce agent / swarm router
  * conversational memory
  * department transfer + escalation logic
  * sentiment + interruption handling

The :class:`VoiceSessionManager` keeps a registry of active sessions with
metrics for observability.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.agents.profiles import PROFILES_BY_DEPARTMENT
from app.agents.prompts import render_system_prompt
from app.core.logging import logger
from app.core.types import Channel, Department, EscalationLevel
from app.memory.manager import memory_manager
from app.models.schemas import Message, SessionContext
from app.models.schemas import Role as RoleEnum
from app.swarms.router import workforce_router
from app.telemetry.metrics import (
    escalations_total,
    voice_sessions_active,
    voice_turn_latency_seconds,
)
from app.voice.gateway import voice_gateway


@dataclass(slots=True)
class VoiceSession:
    session_id: str
    user_id: str
    tenant_id: str | None
    department: Department
    language: str = "en"
    realtime_provider: str = ""
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    transcripts: list[str] = field(default_factory=list)
    escalation: EscalationLevel = EscalationLevel.NONE
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_activity = time.time()


class VoiceSessionManager:
    """Tracks active voice sessions and dispatches conversational turns."""

    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSession] = {}
        self._lock = asyncio.Lock()

    # ---- Lifecycle -----------------------------------------------------

    async def open(
        self,
        *,
        user_id: str,
        tenant_id: str | None,
        department: Department,
        language: str = "en",
        provider: str | None = None,
    ) -> VoiceSession:
        rt = voice_gateway().realtime(provider)
        session_id = uuid4().hex
        sess = VoiceSession(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            department=department,
            language=language,
            realtime_provider=rt.name,
        )
        async with self._lock:
            self._sessions[session_id] = sess
        voice_sessions_active.inc()
        logger.info(
            "Voice session opened id={} dept={} provider={}",
            session_id,
            department.value,
            rt.name,
        )
        return sess

    async def close(self, session_id: str) -> None:
        async with self._lock:
            sess = self._sessions.pop(session_id, None)
        if sess:
            voice_sessions_active.dec()
            logger.info("Voice session closed id={}", session_id)

    def get(self, session_id: str) -> VoiceSession | None:
        return self._sessions.get(session_id)

    def all(self) -> list[VoiceSession]:
        return list(self._sessions.values())

    # ---- Conversational turn ------------------------------------------

    async def handle_user_utterance(
        self, session: VoiceSession, text: str
    ) -> tuple[str, EscalationLevel, Department | None]:
        """Run a single voice conversational turn.

        Returns (agent_text, escalation_level, transferred_to).
        """
        session.touch()
        session.transcripts.append(text)
        memory = memory_manager()

        ctx = SessionContext(
            session_id=session.session_id,
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            channel=Channel.VOICE,
            department=session.department,
            language=session.language,
        )
        await memory.record_message(
            ctx,
            Message(
                session_id=session.session_id,
                role=RoleEnum.USER,
                content=text,
                department=session.department,
            ),
        )

        from app.models.schemas import WorkflowRequest

        start = time.perf_counter()
        result = await workforce_router().execute(
            WorkflowRequest(
                task=text,
                department=session.department,
                user_id=session.user_id,
                tenant_id=session.tenant_id,
                context={"channel": "voice", "history": [t for t in session.transcripts[-10:]]},
            )
        )
        voice_turn_latency_seconds.labels(session.realtime_provider).observe(
            (time.perf_counter() - start)
        )

        agent_text = str(result.output) if result.output is not None else "I'm sorry, I couldn't process that."
        escalation, transfer = _detect_control_signals(agent_text)

        if transfer:
            logger.info("Voice session {} transferring to {}", session.session_id, transfer.value)
            session.department = transfer
        if escalation != EscalationLevel.NONE:
            session.escalation = escalation
            escalations_total.labels(session.department.value, escalation.value).inc()

        await memory.record_message(
            ctx,
            Message(
                session_id=session.session_id,
                role=RoleEnum.AGENT,
                content=agent_text,
                department=session.department,
                agent_name=PROFILES_BY_DEPARTMENT[session.department].agent_name,
            ),
        )
        return agent_text, escalation, transfer

    # ---- Realtime helpers ---------------------------------------------

    def system_prompt_for(self, department: Department) -> str:
        return render_system_prompt(PROFILES_BY_DEPARTMENT[department])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_control_signals(text: str) -> tuple[EscalationLevel, Department | None]:
    """Look for ``{"transfer": ...}`` / ``{"escalate": ...}`` JSON directives."""
    escalation = EscalationLevel.NONE
    transfer: Department | None = None
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if "escalate" in payload:
            try:
                escalation = EscalationLevel(payload["escalate"])
            except Exception:
                escalation = EscalationLevel.SUPERVISOR
        if "transfer" in payload:
            try:
                transfer = Department(payload["transfer"])
            except Exception:
                transfer = None
    return escalation, transfer


_manager: VoiceSessionManager | None = None


def voice_session_manager() -> VoiceSessionManager:
    global _manager
    if _manager is None:
        _manager = VoiceSessionManager()
    return _manager
