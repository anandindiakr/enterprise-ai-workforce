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
    ToolCall,
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
    resolve_topic_transfer,
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


# Department → KB category mapping.  None means "no category filter" (Reception
# talks about everything). Add rows as new departments/categories are introduced.
_DEPT_CATEGORY_MAP: dict[str, str | None] = {
    "sales":          "Sales",
    "hr":             "HR",
    "human_resources":"HR",
    "finance":        "Finance",
    "technology":     "IT",
    "marketing":      "Marketing",
    "customer_care":  "Support",
    "support":        "Support",
    "reception":      None,
    "general":        None,
}


async def _db_category_kb_context(category: str, tenant_id: str | None, *, k: int = 4) -> list[str]:
    """Pull ALL docs from a specific KB category — used to ensure dept agents
    always see their own category's content regardless of query semantics.
    Never raises.
    """
    try:
        from sqlalchemy import select

        from app.db.models import KnowledgeDocumentModel
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            stmt = (
                select(KnowledgeDocumentModel)
                .where(KnowledgeDocumentModel.category.ilike(category))
            )
            if tenant_id:
                stmt = stmt.where(KnowledgeDocumentModel.tenant_id == tenant_id)
            stmt = stmt.order_by(KnowledgeDocumentModel.created_at.desc()).limit(k)
            rows = (await session.execute(stmt)).scalars().all()

        return [
            f"[{doc.title} – {category}] {(doc.content or '').strip()[:2000]}"
            for doc in rows
            if (doc.content or "").strip()
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Category KB retrieval skipped: {}", exc)
        return []


_PRODUCT_QUERY_KEYWORDS = {
    "product", "products", "service", "services", "offer", "offers", "offering",
    "offerings", "catalog", "catalogue", "sell", "sells", "selling", "range",
    "pricing", "prices", "price", "menu", "portfolio", "solutions", "items",
}


def _is_product_query(query: str) -> bool:
    words = set(re.findall(r"[a-z]+", query.lower()))
    return bool(words & _PRODUCT_QUERY_KEYWORDS)


async def _retrieve_kb_context(
    query: str,
    tenant_id: str | None = None,
    *,
    k: int = 8,
    department: str | None = None,
) -> str:
    """Return relevant KB snippets as a formatted string.

    Strategy:
    1.  Category-pin  – fetch up to k/2 docs from the agent's own KB category
        so department-specific content (products, policies, etc.) ALWAYS
        surfaces even when the query doesn't semantically match all of them.
    2.  Product-query pin – if the caller is asking about products/services,
        pull EVERY "Products" catalog document (uncapped) so the agent can
        list the full catalog instead of only the top few semantic matches.
    3.  Semantic/keyword search – pull the top-k query-matched snippets.
    4.  Merge  – pinned snippets first, then query-matched, deduped, capped.
    """
    # Category-pinned docs for this department
    dept_cat = _DEPT_CATEGORY_MAP.get(str(department or "").lower())
    dept_snippets: list[str] = []
    if dept_cat:
        dept_snippets = await _db_category_kb_context(dept_cat, tenant_id, k=min(4, k // 2))

    # If the caller is asking about products/services, pin the FULL catalog
    # (not just a handful) so the agent never omits products from the list.
    product_snippets: list[str] = []
    is_product_query = _is_product_query(query)
    if is_product_query:
        product_snippets = await _db_category_kb_context("Products", tenant_id, k=100)

    # Semantic retrieval (vector first, keyword fallback)
    query_snippets = _vector_kb_context(query, tenant_id, k)
    if not query_snippets:
        query_snippets = await _db_keyword_kb_context(query, tenant_id, k)

    # Merge deduped (pinned snippets win any tie)
    seen: set[str] = set()
    merged: list[str] = []
    for snippet in dept_snippets + product_snippets + query_snippets:
        key = snippet[:120]
        if key not in seen:
            seen.add(key)
            merged.append(snippet)

    # Uncap the result when it's a product listing query so the full catalog
    # reaches the model instead of being truncated to the default k.
    effective_cap = max(k, len(product_snippets) + len(dept_snippets)) if is_product_query else k
    return "\n\n".join(merged[:effective_cap])


class ChatService:
    """Encapsulates a single chat turn (REST or WS)."""

    async def handle(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or uuid4().hex
        memory = memory_manager()
        router = workforce_router()

        # Pull recent history once: used for department-stickiness, first-turn
        # detection, and RAG context.
        prior_history = await memory.recent_history(session_id, limit=10)

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

        # first_turn is True when THIS department has never responded yet.
        # This handles both brand-new sessions AND transfers to a new department:
        # the incoming agent will introduce themselves once, then stay silent on
        # the intro for subsequent turns.
        dept_agent_msgs = [
            m for m in prior_history
            if m.role == Role.AGENT and str(getattr(m, "department", "")) == str(department)
        ]
        first_turn = len(dept_agent_msgs) == 0

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
            from app.core.broadcast import bus

            await bus.publish("orchestration", {
                "type": "agent_active",
                "department": department.value,
                "session_id": session_id,
                "channel": "chat",
                "ts": time.time(),
            })

            # Augment the task with relevant knowledge-base context (RAG) so
            # agents (esp. Sales/Marketing/Care) can answer about uploaded
            # products, policies and documents.
            task = request.message
            kb = await _retrieve_kb_context(request.message, request.tenant_id, department=str(department))
            if kb:
                task = (
                    f"{request.message}\n\n"
                    f"[Enterprise knowledge base — use to answer accurately]\n{kb}"
                )

            # Real actions: let the agent actually DO something (CRM/ticket/
            # calendar/email/outbound-call/social-draft) instead of only
            # talking. Never blocks/fails the turn — degrades to no-op.
            from app.services.action_dispatcher import dispatch as dispatch_actions

            action_context, action_results = await dispatch_actions(
                department=department,
                message=request.message,
                session_id=session_id,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                history=prior_history,
            )
            if action_context:
                task = f"{task}\n\n{action_context}"

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

            # Topic-routing fallback: when the user's message clearly belongs to
            # a different department (keyword match) but neither the LLM nor the
            # explicit-transfer detector routed it, hand off deterministically.
            # Guard rails (in resolve_topic_transfer): only real topic owners
            # are targets (never Reception), no self-transfers, and a
            # substantive agent answer is never overwritten.
            if transferred is None:
                topic_dept = resolve_topic_transfer(department, request.message, text)
                if topic_dept is not None:
                    transferred = topic_dept
                    text = ""  # force the natural handoff phrase below

            if escalation != EscalationLevel.NONE:
                escalations_total.labels(department.value, escalation.value).inc()
            final_dept = transferred or department

            if transferred is not None:
                await bus.publish("orchestration", {
                    "type": "handoff",
                    "from_department": department.value,
                    "to_department": transferred.value,
                    "session_id": session_id,
                    "channel": "chat",
                    "ts": time.time(),
                })

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
                tool_calls=[
                    ToolCall(
                        name=f"{r.connector}.{r.tool}",
                        result=r.summary,
                        success=r.success,
                    )
                    for r in action_results
                ],
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

        # first_turn = True when this specific department hasn't spoken yet
        # (handles both session start and post-transfer introductions).
        dept_agent_msgs = [
            m for m in prior_history
            if m.role == Role.AGENT and str(getattr(m, "department", "")) == str(department)
        ]
        first_turn = len(dept_agent_msgs) == 0

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
            text = f"Sure thing! Let me connect you with our {label} team right now — one moment."
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
                kb = await _retrieve_kb_context(request.message, request.tenant_id, department=str(department))
                if kb:
                    system_prompt += "\n\n# Enterprise knowledge base (use this to answer)\n" + kb
                else:
                    system_prompt += (
                        "\n\n# Enterprise knowledge base\n(No matching documents found for this "
                        "query — do NOT invent products, services, or details. If the caller's "
                        "question needs specific info you don't have, say so and offer to connect "
                        "them to someone who can help.)"
                    )

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
                    temperature=0.5,  # lower to reduce hallucinated/off-topic content on live calls
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

        # Topic-routing fallback (same guard rails as the full handler): if the
        # caller's message clearly belongs to another department and the fast
        # reply shows the current agent couldn't actually help, hand off
        # deterministically so live phone calls (Asterisk/Singtel) route topics
        # the same way chat does.
        if leaked_transfer is None:
            topic = resolve_topic_transfer(department, request.message, text)
            if topic is not None:
                label = dept_labels.get(topic.value, topic.value.replace("_", " ").title())
                handoff = f"Sure thing! Let me connect you with our {label} team right now — one moment."
                agent_msg = Message(
                    session_id=session_id,
                    role=Role.AGENT,
                    content=handoff,
                    department=topic,
                    agent_name=PROFILES_BY_DEPARTMENT[topic].agent_name,
                )
                await memory.record_message(ctx, agent_msg)
                return ChatResponse(
                    session_id=session_id,
                    message=agent_msg,
                    agent_name=agent_msg.agent_name or "Workforce",
                    department=topic,
                    escalation=EscalationLevel.NONE,
                    transferred_to=topic,
                )

        # If the model leaked a transfer to a *different* department, perform the
        # hand-off deterministically instead of speaking the JSON.
        if leaked_transfer is not None and leaked_transfer != department:
            target = leaked_transfer
            target_profile = PROFILES_BY_DEPARTMENT.get(target)
            handoff = f"Sure thing! Let me connect you with our {target.value.title()} team right now — one moment."
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

        # Route un-pinned messages through the keyword router instead of always
        # defaulting to Reception, so a bare "I need help with my invoice" lands
        # with Finance rather than the front desk.
        from app.swarms.router import workforce_router

        department = request.department or workforce_router().choose_department(request.message)
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
        # only introduces itself once per department (first_turn == this dept
        # hasn't spoken yet, handles both session-start and post-transfer intros).
        prior_history = await memory.recent_history(session_id, limit=12)
        dept_agent_msgs_stream = [
            m for m in prior_history
            if m.role == Role.AGENT and str(getattr(m, "department", "")) == str(department)
        ]
        first_turn = len(dept_agent_msgs_stream) == 0

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
