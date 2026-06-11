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


_KB_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for",
    "is", "are", "was", "were", "be", "do", "does", "did", "with", "what",
    "which", "who", "how", "can", "could", "would", "should", "i", "you",
    "we", "they", "it", "this", "that", "your", "our", "my", "me", "us",
    "about", "tell", "please", "want", "need", "know", "have", "has",
}


def _vector_kb_context(query: str, tenant_id: str | None, k: int) -> list[str]:
    """Vector (ChromaDB) retrieval. Returns a list of formatted snippets."""
    try:
        from app.memory.long_term import long_term_memory

        where = {"tenant_id": tenant_id} if tenant_id else None
        try:
            hits = long_term_memory().search(query, k=k, where=where)
        except Exception:
            hits = long_term_memory().search(query, k=k)

        snippets: list[str] = []
        for h in hits:
            txt = (h.get("text") or "").strip()
            if not txt:
                continue
            title = (h.get("metadata") or {}).get("title", "document")
            snippets.append(f"[{title}] {txt[:2000]}")
        return snippets
    except Exception as exc:  # noqa: BLE001
        logger.debug("Vector KB retrieval skipped: {}", exc)
        return []


async def _db_keyword_kb_context(query: str, tenant_id: str | None, k: int) -> list[str]:
    """Postgres keyword-search fallback over ``KnowledgeDocumentModel.content``.

    This guarantees agents can see uploaded documents even when vector
    embeddings are unavailable (Chroma down / sentence-transformers missing).
    Never raises.
    """
    try:
        from sqlalchemy import or_, select

        from app.db.models import KnowledgeDocumentModel
        from app.db.session import AsyncSessionLocal

        keywords = [
            w for w in re.findall(r"[A-Za-z0-9]+", query.lower())
            if len(w) > 2 and w not in _KB_STOPWORDS
        ][:8]

        async with AsyncSessionLocal() as session:
            stmt = select(KnowledgeDocumentModel)
            if tenant_id:
                stmt = stmt.where(KnowledgeDocumentModel.tenant_id == tenant_id)
            if keywords:
                stmt = stmt.where(
                    or_(*[
                        KnowledgeDocumentModel.content.ilike(f"%{w}%")
                        for w in keywords
                    ])
                )
            stmt = stmt.order_by(KnowledgeDocumentModel.created_at.desc()).limit(max(k * 3, 15))
            rows = (await session.execute(stmt)).scalars().all()

        # Rank by how many distinct keywords appear in the content.
        scored: list[tuple[int, str]] = []
        for doc in rows:
            content = (doc.content or "").strip()
            if not content:
                continue
            lc = content.lower()
            score = sum(1 for w in keywords if w in lc) if keywords else 1
            scored.append((score, f"[{doc.title}] {content[:2000]}"))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [s for _, s in scored[:k]]
    except Exception as exc:  # noqa: BLE001
        logger.debug("DB keyword KB retrieval skipped: {}", exc)
        return []


async def _retrieve_kb_context(query: str, tenant_id: str | None = None, *, k: int = 8) -> str:
    """Best-effort retrieval of relevant knowledge-base snippets.

    Tries semantic (vector) search first, then falls back to a Postgres
    keyword search so uploaded documents are always reachable even when
    embeddings are unavailable. Returns a formatted string of the top
    matches, or "" if nothing relevant is found. Never raises — RAG is an
    enhancement, not a hard dependency of a chat turn.
    """
    snippets = _vector_kb_context(query, tenant_id, k)
    if not snippets:
        snippets = await _db_keyword_kb_context(query, tenant_id, k)
    return "\n\n".join(snippets[:k])


class ChatService:
    """Encapsulates a single chat turn (REST or WS)."""

    async def handle(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or uuid4().hex
        memory = memory_manager()
        router = workforce_router()

        # Pull recent history once: used both for first-turn detection AND to
        # make the active department "sticky" across turns. Without this the
        # department was re-guessed from each message, so a transfer reset back
        # to the keyword-matched department on the very next turn.
        prior_history = await memory.recent_history(session_id, limit=10)
        first_turn = len(prior_history) == 0

        session_department: Department | None = None
        for msg in reversed(prior_history):
            if msg.role == Role.AGENT and msg.department:
                try:
                    session_department = (
                        msg.department
                        if isinstance(msg.department, Department)
                        else Department(msg.department)
                    )
                except Exception:  # noqa: BLE001
                    session_department = None
                break

        # Department precedence: explicit request > sticky session dept >
        # keyword routing on the message text.
        department = (
            request.department
            or session_department
            or router.choose_department(request.message)
        )

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
            # Augment the task with relevant knowledge-base context (RAG) so
            # agents (esp. Sales/Marketing/Care) can answer about uploaded
            # products, policies and documents.
            task = request.message
            kb = await _retrieve_kb_context(request.message, request.tenant_id)
            if kb:
                task = (
                    f"{request.message}\n\n"
                    f"[Enterprise knowledge base — use to answer accurately]\n{kb}"
                )

            wf = await router.execute(
                WorkflowRequest(
                    task=task,
                    department=department,
                    user_id=request.user_id,
                    tenant_id=request.tenant_id,
                    context={**(request.metadata or {}), "first_turn": first_turn},
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

            # An agent saying "let me connect you with sales" while it IS the
            # sales agent is not a real transfer. Ignore self-transfers so we
            # don't loop the handoff phrase or wipe the agent's real answer.
            if transferred is not None and transferred == department:
                transferred = None

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

            # If a control directive stripped the entire message, synthesise a
            # natural phrase: a handoff line for a real transfer, otherwise an
            # in-department acknowledgement (so the reply is never blank).
            if not text.strip():
                dept_labels = {
                    "reception": "Reception", "customer_care": "Customer Care",
                    "sales": "Sales", "hr": "Human Resources", "finance": "Finance",
                    "technology": "Technology", "marketing": "Marketing",
                }
                _key = str(final_dept.value if hasattr(final_dept, "value") else final_dept)
                label = dept_labels.get(_key, str(final_dept).replace("_", " ").title())
                if transferred:
                    text = f"Let me connect you with our {label} team right away."
                else:
                    text = f"You're with our {label} team. How can I help you today?"

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

    async def handle_fast(self, request: ChatRequest) -> ChatResponse:
        """Low-latency single-turn handler optimised for *voice*.

        Voice conversations need sub-2s turns. The full Swarms hierarchy
        (``handle``) runs agent loops + tool calls and can take 5-15s, which
        makes a spoken conversation feel broken. ``handle_fast`` instead:

        * resolves the sticky department exactly like ``handle``;
        * honours an explicit transfer request **deterministically** (no LLM
          round-trip) so "transfer me to finance" switches instantly;
        * otherwise issues a single direct OpenAI call (gpt-4o-mini) with the
          department system prompt, knowledge-base context and recent history.

        Falls back to ``handle`` when no OpenAI key is configured.
        """
        import os

        from app.core.config import settings

        session_id = request.session_id or uuid4().hex
        memory = memory_manager()
        router = workforce_router()

        prior_history = await memory.recent_history(session_id, limit=12)
        first_turn = len(prior_history) == 0

        session_department: Department | None = None
        for msg in reversed(prior_history):
            if msg.role == Role.AGENT and msg.department:
                try:
                    session_department = (
                        msg.department
                        if isinstance(msg.department, Department)
                        else Department(msg.department)
                    )
                except Exception:  # noqa: BLE001
                    session_department = None
                break

        department = (
            request.department
            or session_department
            or router.choose_department(request.message)
        )

        ctx = SessionContext(
            session_id=session_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            channel=Channel.VOICE,
            department=department,
            metadata=request.metadata,
        )

        # Persist the user message up front.
        await memory.record_message(
            ctx,
            Message(
                session_id=session_id,
                role=Role.USER,
                content=request.message,
                department=department,
            ),
        )

        dept_labels = {
            "reception": "Reception", "customer_care": "Customer Care",
            "sales": "Sales", "hr": "Human Resources", "finance": "Finance",
            "technology": "Technology", "marketing": "Marketing",
        }

        # 1) Deterministic transfer — instant, no LLM. Switch department and
        #    return a short spoken handoff phrase. The caller (voice page) then
        #    runs a follow-up turn against the NEW department so it actually
        #    answers out loud.
        intent = detect_transfer_intent(request.message)
        if intent is not None and intent != department:
            label = dept_labels.get(intent.value, intent.value.replace("_", " ").title())
            text = f"Of course — connecting you to our {label} team now."
            agent_msg = Message(
                session_id=session_id,
                role=Role.AGENT,
                content=text,
                department=intent,  # record under target so it becomes sticky
                agent_name=PROFILES_BY_DEPARTMENT[intent].agent_name,
            )
            await memory.record_message(ctx, agent_msg)
            return ChatResponse(
                session_id=session_id,
                message=agent_msg,
                agent_name=agent_msg.agent_name or "Workforce",
                department=intent,
                escalation=EscalationLevel.NONE,
                transferred_to=intent,
            )

        # 2) Single fast LLM reply.
        start = time.perf_counter()
        text = ""
        openai_key = getattr(settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            try:
                from openai import AsyncOpenAI

                from app.agents.prompts import build_system_prompt

                profile = PROFILES_BY_DEPARTMENT.get(department)
                system_prompt = (
                    await build_system_prompt(profile, first_turn=first_turn, voice=True,
                                              tenant_id=request.tenant_id or "default")
                    if profile else "You are a helpful AI assistant."
                )
                kb = await _retrieve_kb_context(request.message, request.tenant_id)
                if kb:
                    system_prompt += "\n\n# Enterprise knowledge base (use this to answer)\n" + kb

                messages: list[dict] = [{"role": "system", "content": system_prompt}]
                for msg in prior_history:
                    role_val = getattr(msg.role, "value", msg.role)
                    oai_role = "assistant" if role_val in ("agent", "assistant") else "user"
                    if msg.content:
                        messages.append({"role": oai_role, "content": msg.content})
                messages.append({"role": "user", "content": request.message})

                client = AsyncOpenAI(api_key=openai_key)
                completion = await client.chat.completions.create(
                    model=getattr(settings, "openai_model", "gpt-4o-mini"),
                    messages=messages,
                    temperature=0.6,
                    max_tokens=400,  # keep spoken replies concise
                )
                text = (completion.choices[0].message.content or "").strip()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fast voice LLM failed, falling back to full handler: {}", exc)
                text = ""

        if not text:
            # No key or LLM failed → use the full (slower) handler so the user
            # still gets a real answer rather than silence.
            return await self.handle(request)

        # Defence in depth: even though the voice prompt forbids JSON/directives,
        # parse and STRIP any control signals the model may have leaked so they
        # are never spoken aloud by TTS. A leaked transfer is honoured as a real
        # hand-off; a leaked escalation sets the escalation level.
        from app.voice.session import _detect_control_signals, _strip_control_signals

        leaked_escalation, leaked_transfer = _detect_control_signals(text)
        text = _strip_control_signals(text)

        chat_latency_seconds.labels(department.value).observe(time.perf_counter() - start)
        chat_requests_total.labels(department.value, "success").inc()

        # If the model leaked a transfer to a *different* department, perform the
        # hand-off deterministically instead of speaking the JSON.
        if leaked_transfer is not None and leaked_transfer != department:
            target = leaked_transfer
            target_profile = PROFILES_BY_DEPARTMENT.get(target)
            handoff = f"Of course — connecting you to our {target.value.title()} team now."
            agent_msg = Message(
                session_id=session_id,
                role=Role.AGENT,
                content=handoff,
                department=target,
                agent_name=getattr(target_profile, "agent_name", None) or "Workforce",
            )
            await memory.record_message(ctx, agent_msg)
            return ChatResponse(
                session_id=session_id,
                message=agent_msg,
                agent_name=agent_msg.agent_name or "Workforce",
                department=target,
                escalation=leaked_escalation,
                transferred_to=target,
            )

        # If stripping the directives left nothing to say, synthesise a short,
        # natural in-department reply rather than going silent.
        if not text.strip():
            text = "I'm here and happy to help — could you tell me a bit more about what you need?"

        agent_msg = Message(
            session_id=session_id,
            role=Role.AGENT,
            content=text,
            department=department,
            agent_name=PROFILES_BY_DEPARTMENT[department].agent_name,
        )
        await memory.record_message(ctx, agent_msg)
        return ChatResponse(
            session_id=session_id,
            message=agent_msg,
            agent_name=agent_msg.agent_name or "Workforce",
            department=department,
            escalation=leaked_escalation,
            transferred_to=None,
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
        from app.agents.prompts import build_system_prompt
        from app.core.types import Department

        department = request.department or Department.RECEPTION
        profile = PROFILES_BY_DEPARTMENT.get(department)

        session_id = request.session_id or uuid4().hex
        memory = memory_manager()
        ctx = SessionContext(
            session_id=session_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            channel=Channel.CHAT,
            department=department,
            metadata=request.metadata,
        )

        # Pull recent conversation so the model keeps context across turns and
        # only introduces itself once (first_turn == no prior history).
        prior_history = await memory.recent_history(session_id, limit=12)
        first_turn = len(prior_history) == 0

        system_prompt = (
            await build_system_prompt(profile, first_turn=first_turn,
                                      tenant_id=request.tenant_id or "default")
            if profile
            else "You are a helpful AI assistant."
        )

        # Inject knowledge-base context so the agent can answer about products,
        # policies, etc. that the enterprise has uploaded.
        kb = await _retrieve_kb_context(request.message, request.tenant_id)
        if kb:
            system_prompt += (
                "\n\n# Enterprise knowledge base (use this to answer)\n" + kb
            )

        # Build the OpenAI message list: system + prior turns + current message.
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for msg in prior_history:
            role_val = getattr(msg.role, "value", msg.role)
            oai_role = "assistant" if role_val in ("agent", "assistant") else "user"
            if msg.content:
                messages.append({"role": oai_role, "content": msg.content})
        messages.append({"role": "user", "content": request.message})

        # Persist the user message before streaming the answer.
        await memory.record_message(
            ctx,
            Message(session_id=session_id, role=Role.USER, content=request.message),
        )

        client = AsyncOpenAI(api_key=openai_key)
        stream = await client.chat.completions.create(
            model=getattr(settings, "openai_model", "gpt-4o-mini"),
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=1024,
        )
        chunks: list[str] = []
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                chunks.append(delta)
                yield delta

        # Persist the assistant reply so the next turn has continuity.
        full = "".join(chunks).strip()
        if full:
            await memory.record_message(
                ctx,
                Message(session_id=session_id, role=Role.AGENT, content=full),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI streaming failed, falling back: {}", exc)
        resp = await chat_service().handle(request)
        yield resp.message.content or ""
