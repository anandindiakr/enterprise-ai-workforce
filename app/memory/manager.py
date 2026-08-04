"""Cross-agent shared memory and conversation summarization helpers."""

from __future__ import annotations

from typing import Any

from app.core.logging import logger
from app.memory.long_term import long_term_memory
from app.memory.short_term import short_term_memory
from app.models.schemas import Message, SessionContext

# Session IDs we've already confirmed/created in the durable DB this process
# lifetime, so we don't hit the DB with a lookup on every single message.
_KNOWN_DB_SESSIONS: set[str] = set()


class MemoryManager:
    """Facade combining short-term + long-term memory for agents."""

    def __init__(self) -> None:
        self.short = short_term_memory()
        self.long = long_term_memory()

    async def record_message(self, ctx: SessionContext, message: Message) -> None:
        await self.short.append_message(ctx.session_id, message)
        await self._persist_durable(ctx, message)

    async def _persist_durable(self, ctx: SessionContext, message: Message) -> None:
        """Mirror the message into Postgres (ChatSessionModel/ChatMessageModel)
        so admins have a real, browsable, per-tenant communication log/history
        -- independent of the ephemeral short-term (Redis/in-memory) store used
        for live conversational context.

        Best-effort only: never raises, never blocks/breaks the chat turn.
        """
        try:
            import uuid

            from app.db import crud
            from app.db.session import AsyncSessionLocal

            # Session ids from non-chat channels (e.g. Vapi call ids like
            # "call_abc123") aren't valid UUIDs. Deterministically derive a
            # stable UUID5 so every channel's history is still persisted and
            # remains stable/lookup-able across turns of the same call/chat.
            try:
                db_session_id = str(uuid.UUID(ctx.session_id))
            except (ValueError, AttributeError):
                db_session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, ctx.session_id))

            department_value = (
                message.department.value
                if hasattr(message.department, "value")
                else (message.department or (
                    ctx.department.value if hasattr(ctx.department, "value") else ctx.department
                ))
            )
            tenant_id = ctx.tenant_id or "default"

            async with AsyncSessionLocal() as db:
                if db_session_id not in _KNOWN_DB_SESSIONS:
                    existing = await crud.get_chat_session(db, db_session_id)
                    if existing is None:
                        await crud.create_chat_session(
                            db,
                            session_id=db_session_id,
                            user_id=ctx.user_id,
                            tenant_id=tenant_id,
                            department=str(department_value or "reception"),
                            metadata={"original_session_id": ctx.session_id},
                        )
                    _KNOWN_DB_SESSIONS.add(db_session_id)

                await crud.add_chat_message(
                    db,
                    session_id=db_session_id,
                    role=message.role.value if hasattr(message.role, "value") else str(message.role),
                    content=message.content,
                    department=str(department_value) if department_value else None,
                    agent_name=message.agent_name,
                )
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Durable chat history persistence skipped: {}", exc)

    async def recent_history(self, session_id: str, limit: int = 30) -> list[Message]:
        return await self.short.get_history(session_id, limit=limit)

    def remember_fact(
        self,
        text: str,
        *,
        tenant_id: str | None,
        department: str | None,
        agent: str | None,
        kind: str = "fact",
    ) -> str:
        return self.long.upsert(
            text,
            metadata={
                "tenant_id": tenant_id or "default",
                "department": department or "shared",
                "agent": agent or "shared",
                "kind": kind,
            },
        )

    def retrieve_context(
        self,
        query: str,
        *,
        tenant_id: str | None = None,
        department: str | None = None,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        where: dict[str, Any] = {}
        if tenant_id:
            where["tenant_id"] = tenant_id
        if department:
            where["department"] = department
        return self.long.search(query, k=k, where=where or None)


_manager: MemoryManager | None = None


def memory_manager() -> MemoryManager:
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
