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
from app.voice.session import _detect_control_signals  # reuse signal parser

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
            if escalation != EscalationLevel.NONE:
                escalations_total.labels(department.value, escalation.value).inc()
            final_dept = transferred or department

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
