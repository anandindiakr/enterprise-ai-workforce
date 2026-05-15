"""Cross-agent shared memory and conversation summarization helpers."""

from __future__ import annotations

from typing import Any

from app.memory.long_term import long_term_memory
from app.memory.short_term import short_term_memory
from app.models.schemas import Message, SessionContext


class MemoryManager:
    """Facade combining short-term + long-term memory for agents."""

    def __init__(self) -> None:
        self.short = short_term_memory()
        self.long = long_term_memory()

    async def record_message(self, ctx: SessionContext, message: Message) -> None:
        await self.short.append_message(ctx.session_id, message)

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
