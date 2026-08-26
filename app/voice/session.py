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
import re
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

        # Introduce the active department's agent only the first time it speaks
        # in this session (handles fresh sessions AND post-transfer handoffs).
        introduced = session.metadata.setdefault("introduced_departments", [])
        first_turn = session.department.value not in introduced
        if first_turn:
            introduced.append(session.department.value)

        start = time.perf_counter()
        # Inject knowledge-base context so voice agents (esp. Sales/Marketing/
        # Care) answer from uploaded documents, not just generic knowledge.
        task = text
        try:
            from app.services.chat_service import _retrieve_kb_context

            kb = await _retrieve_kb_context(text, session.tenant_id)
            if kb:
                task = (
                    f"{text}\n\n"
                    f"[Enterprise knowledge base — use to answer accurately]\n{kb}"
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Voice KB retrieval skipped: {}", exc)

        result = await workforce_router().execute(
            WorkflowRequest(
                task=task,
                department=session.department,
                user_id=session.user_id,
                tenant_id=session.tenant_id,
                context={
                    "channel": "voice",
                    "history": [t for t in session.transcripts[-10:]],
                    "first_turn": first_turn,
                },
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


# Matches embedded/fenced JSON control directives anywhere in the text, e.g.
#   {"transfer": "sales"}   or   {"escalate": "supervisor"}
_JSON_DIRECTIVE_RE = re.compile(
    r'\{\s*"(?:transfer|escalate)"\s*:\s*"[^"]+"\s*\}'
)

# Prose leak patterns the LLM sometimes emits instead of/alongside JSON, e.g.
#   "User requested to transfer to sales department!"
#   "Transferring you to the finance team."
_PROSE_TRANSFER_RE = re.compile(
    r'(?:transfer(?:ring)?|connect(?:ing)?|routing|redirect(?:ing)?|hand(?:ing)?\s+off)'
    r'[^.\n]*?\bto\b[^.\n]*?\b(reception|customer[\s_]?care|sales|hr|human\s+resources?|'
    r'finance|billing|accounting|technolog\w*|tech(?:nical)?\s+support|it\s+support|'
    r'marketing)\b',
    re.IGNORECASE,
)

# Department keyword synonyms used by both the prose detector and the
# deterministic user-intent detector.
_DEPT_SYNONYMS: tuple[tuple[Department, tuple[str, ...]], ...] = (
    (Department.SALES, ("sales", "pricing", "purchase", "buy a", "quote")),
    (Department.HR, ("human resources", "human resource", " hr ", "hr department",
                     "recruit", "hiring", "payroll", "benefits")),
    (Department.FINANCE, ("finance", "billing", "invoice", "accounting",
                          "refund", "payment")),
    (Department.TECHNOLOGY, ("technology", "tech support", "technical support",
                             "it support", "it department", "engineer")),
    (Department.MARKETING, ("marketing", "campaign", "branding", "social media")),
    (Department.CUSTOMER_CARE, ("customer care", "customer service",
                                "customer support", "complaint")),
    (Department.RECEPTION, ("reception", "receptionist", "front desk", "operator")),
)

# Explicit transfer-request triggers in a *user* utterance.
_TRANSFER_TRIGGERS: tuple[str, ...] = (
    "transfer", "connect me", "connect to", "route me", "speak to", "speak with",
    "talk to", "talk with", "put me through", "switch me", "redirect", "hand me",
    "i want to talk", "i need to speak", "i want to speak", "get me", "reach the",
    "can you connect", "send me to",
)


def _match_department(text: str) -> Department | None:
    """Resolve a department from free-form text using keyword synonyms."""
    lowered = f" {text.lower()} "
    for dept, needles in _DEPT_SYNONYMS:
        if any(n in lowered for n in needles):
            return dept
    return None


# Phrases that signal an agent replied without actually being able to help.
# Used by the topic-routing fallback so a cross-department request that the
# current agent punted on is handed off deterministically instead of leaving
# the user stuck with a generic "I don't have access" reply.
_REFUSAL_MARKERS = (
    "don't have access", "do not have access", "don't have direct access",
    "do not have direct access", "no access to", "can't help", "cannot help",
    "can't assist", "cannot assist", "unable to", "not able to",
    "don't have the", "do not have the", "doesn't have", "does not have",
    "don't have information", "no information on", "no data on",
    "could you please provide", "please provide details",
)

# Replies shorter than this (after stripping) are treated as a punt / clarifying
# question, so a deterministic topic transfer may override them. Longer replies
# are treated as real answers and are NEVER overwritten.
_PUNT_MAX_LEN = 100


def resolve_topic_transfer(
    current: Department,
    message: str,
    agent_reply: str,
) -> Department | None:
    """Deterministic topic-based hand-off, or ``None``.

    The enterprise-orchestration guard rails:

    * only fires for a *real* topic owner -- never Reception, which is the
      keyword router's catch-all default, not a topic (prevents bouncing
      unmatched messages to the front desk);
    * never self-transfers (target must differ from the current department);
    * only overrides the agent when it actually punted -- the reply is empty,
      shorter than :data:`_PUNT_MAX_LEN`, or contains a refusal marker -- so a
      substantive answer is never wiped.

    This is the deterministic layer under the LLM's own ``transfer`` directive:
    it catches cross-department requests that the model failed to hand off.
    """
    topic = workforce_router().choose_department(message)
    if topic is None or topic == Department.RECEPTION or topic == current:
        return None
    reply = (agent_reply or "").strip().lower()
    if not reply:
        return topic
    if len(reply) < _PUNT_MAX_LEN:
        return topic
    if any(marker in reply for marker in _REFUSAL_MARKERS):
        return topic
    return None


def detect_transfer_intent(user_text: str) -> Department | None:
    """Deterministically detect an explicit transfer request in a *user* message.

    This does not rely on the LLM emitting a JSON directive; it recognises
    natural phrasing such as "transfer me to sales" or "I want to talk to HR".
    Returns the target :class:`Department` or ``None``.
    """
    if not user_text:
        return None
    lowered = user_text.lower()
    if not any(trigger in lowered for trigger in _TRANSFER_TRIGGERS):
        return None
    return _match_department(user_text)


def _detect_control_signals(text: str) -> tuple[EscalationLevel, Department | None]:
    """Detect ``transfer`` / ``escalate`` directives from agent output.

    Handles bare JSON lines, JSON embedded inside prose or markdown fences,
    and natural-language prose leaks the LLM occasionally produces.
    """
    escalation = EscalationLevel.NONE
    transfer: Department | None = None

    # 1) JSON directives anywhere in the text (line-based or embedded).
    for match in _JSON_DIRECTIVE_RE.finditer(text):
        try:
            payload = json.loads(match.group(0))
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

    # 2) Prose leak fallback ("transferring you to the sales team").
    if transfer is None:
        prose = _PROSE_TRANSFER_RE.search(text)
        if prose:
            transfer = _match_department(prose.group(1))

    return escalation, transfer


def _strip_control_signals(text: str) -> str:
    """Remove control directives from agent text before display or TTS.

    Removes bare JSON directive lines, embedded/fenced JSON directives, and
    prose transfer leaks so none of them are ever shown or spoken to the user.
    """
    # Drop embedded JSON directives anywhere in the text.
    text = _JSON_DIRECTIVE_RE.sub("", text)

    clean = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            clean.append(line)
            continue
        # Bare JSON directive line.
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                payload = json.loads(stripped)
                if "transfer" in payload or "escalate" in payload:
                    continue
            except Exception:
                pass
        # Markdown code-fence wrappers around stripped JSON become empty.
        if stripped in ("```", "```json"):
            continue
        # Prose transfer leak line.
        if _PROSE_TRANSFER_RE.search(stripped):
            continue
        clean.append(line)
    return "\n".join(clean).strip()


_manager: VoiceSessionManager | None = None


def voice_session_manager() -> VoiceSessionManager:
    global _manager
    if _manager is None:
        _manager = VoiceSessionManager()
    return _manager
