"""Chat service -- glues conversational requests to the SwarmRouter."""

from __future__ import annotations

import re
import time
from uuid import uuid4

from app.agents.profiles import PROFILES_BY_DEPARTMENT
from app.core.logging import logger
from app.core.types import Channel, Department, EscalationLevel, Role
from app.memory.manager import memory_manager
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    Message,
    SessionContext,
    WorkflowRequest,
)
from app.swarms.router import workforce_router
from app.telemetry.metrics import (
    chat_latency_seconds,
    chat_requests_total,
    escalations_total,
)
from app.voice.session import (
    _detect_control_signals,
    _strip_control_signals,
    detect_transfer_intent,
)

# Swarms agent.run() returns the raw conversation accumulation:
#   {task}\n[{tool_calls_json}]\nFunction '{name}' result:\n{json}\n{response}
# We extract only the final natural-language response after the last tool block.
_FUNC_RESULT_RE = re.compile(
    r"Function '[^']+' result:\s*\{.*?\}",
    re.DOTALL,
)


def _extract_agent_text(raw: str, task: str = "") -> str:
    """Thin wrapper around the shared utility for backward compatibility."""
    from app.core.agent_output import extract_agent_text
    return extract_agent_text(raw, task=task)


class ChatService:
    """Encapsulates a single chat turn (REST or WS)."""

    async def handle(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or uuid4().hex
        memory = memory_manager()
        router = workforce_router()
        department = request.department or router.choose_department(request.message)

        ctx = SessionContext(
            session_id=session_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            channel=Channel.CHAT,
            department=department,
            metadata=request.metadata,
        )

        # Persist the user message
        await memory.record_message(
            ctx,
            Message(
                session_id=session_id,
                role=Role.USER,
                content=request.message,
                attachments=request.attachments,
                department=department,
            ),
        )

        start = time.perf_counter()
        try:
            wf = await router.execute(
                WorkflowRequest(
                    task=request.message,
                    department=department,
                    user_id=request.user_id,
                    tenant_id=request.tenant_id,
                    context=request.metadata,
                )
            )
            duration = time.perf_counter() - start
            chat_latency_seconds.labels(department.value).observe(duration)
            chat_requests_total.labels(
                department.value, "success" if wf.succeeded else "error"
            ).inc()

            text = _extract_agent_text(str(wf.output) if wf.output is not None else "", task=request.message)
            escalation, transferred = _detect_control_signals(text)
            text = _strip_control_signals(text)  # remove JSON directives before display

            # Deterministic fallback: honour an explicit transfer request in the
            # *user* message even when the LLM never emitted a control directive.
            if transferred is None:
                intent = detect_transfer_intent(request.message)
                if intent is not None and intent != department:
                    transferred = intent
                    text = ""  # force the natural handoff phrase below

            if escalation != EscalationLevel.NONE:
                escalations_total.labels(department.value, escalation.value).inc()
            final_dept = transferred or department

            # If transfer stripped the entire message, provide a natural handoff phrase
            if not text.strip() and transferred:
                dept_labels = {
                    "reception": "Reception", "customer_care": "Customer Care",
                    "sales": "Sales", "hr": "Human Resources", "finance": "Finance",
                    "technology": "Technology", "marketing": "Marketing",
                }
                label = dept_labels.get(
                    str(transferred.value if hasattr(transferred, "value") else transferred),
                    str(transferred).replace("_", " ").title()
                )
                text = f"Let me connect you with our {label} team right away."

            agent_msg = Message(
                session_id=session_id,
                role=Role.AGENT,
                content=text,
                department=final_dept,
                agent_name=PROFILES_BY_DEPARTMENT[final_dept].agent_name,
            )
            await memory.record_message(ctx, agent_msg)

            return ChatResponse(
                session_id=session_id,
                message=agent_msg,
                agent_name=agent_msg.agent_name or "Workforce",
                department=final_dept,
                escalation=escalation,
                transferred_to=transferred,
            )
        except Exception as exc:
            chat_requests_total.labels(department.value, "error").inc()
            logger.exception("Chat handle failed")
            err_msg = Message(
                session_id=session_id,
                role=Role.SYSTEM,
                content=f"Internal error: {exc}",
                department=department,
            )
            return ChatResponse(
                session_id=session_id,
                message=err_msg,
                agent_name="System",
                department=department,
            )


_service: ChatService | None = None


def chat_service() -> ChatService:
    global _service
    if _service is None:
        _service = ChatService()
    return _service


# ─────────────────────────────────────────────────────────────────────────────
# True streaming helper (uses OpenAI stream=True directly, bypasses Swarms)
# ─────────────────────────────────────────────────────────────────────────────

async def stream_chat_tokens(request: ChatRequest):
    """Yield raw text tokens from OpenAI with streaming enabled.

    Falls back to the standard ChatService.handle() if streaming is
    unavailable (no API key, OpenAI import error, etc.).
    """
    import os
    from app.core.config import settings

    openai_key = getattr(settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        # Fallback: return full response as one token
        resp = await chat_service().handle(request)
        yield resp.message.content or ""
        return

    try:
        from openai import AsyncOpenAI
        from app.agents.profiles import PROFILES_BY_DEPARTMENT
        from app.core.types import Department

        department = request.department or Department.RECEPTION
        profile = PROFILES_BY_DEPARTMENT.get(department)
        system_prompt = profile.system_prompt if profile else "You are a helpful AI assistant."

        client = AsyncOpenAI(api_key=openai_key)
        stream = await client.chat.completions.create(
            model=getattr(settings, "openai_model", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": request.message},
            ],
            stream=True,
            temperature=0.7,
            max_tokens=1024,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI streaming failed, falling back: {}", exc)
        resp = await chat_service().handle(request)
        yield resp.message.content or ""
