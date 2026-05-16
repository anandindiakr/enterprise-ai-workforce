"""Celery task definitions.

All tasks are async-friendly: they run sync wrappers around
asyncio.run() where needed so the Celery worker (sync) can
call async services without a running event loop conflict.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: run async code from sync Celery task
# ─────────────────────────────────────────────────────────────────────────────

def _run(coro):
    """Execute an async coroutine from a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────────────
# Voice session cleanup
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.purge_expired_voice_sessions", bind=True)
def purge_expired_voice_sessions(self) -> dict[str, Any]:
    """Remove voice sessions that have been idle for > 1 hour."""
    try:
        from app.voice.session import voice_session_manager
        mgr = voice_session_manager()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        purged = []
        for sid, session in list(mgr._sessions.items()):
            updated = getattr(session, "updated_at", None)
            if updated and updated < cutoff:
                asyncio.run(mgr.close(sid))
                purged.append(sid)
        logger.info("Purged %d expired voice sessions", len(purged))
        return {"purged": len(purged), "ids": purged}
    except Exception as exc:  # noqa: BLE001
        logger.error("purge_expired_voice_sessions failed: %s", exc)
        raise self.retry(exc=exc, countdown=60, max_retries=3)


# ─────────────────────────────────────────────────────────────────────────────
# Analytics snapshot
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.sync_analytics_snapshot", bind=True)
def sync_analytics_snapshot(self) -> dict[str, Any]:
    """Compute platform-wide analytics metrics and store in Redis."""
    try:
        async def _sync():
            from app.memory.short_term import short_term_memory
            redis = short_term_memory()
            if not redis._client:
                await redis.connect()
            snapshot = {
                "computed_at": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
            }
            await redis._client.setex(
                "analytics:snapshot",
                900,
                str(snapshot),
            )
            return snapshot

        result = _run(_sync())
        logger.info("Analytics snapshot updated: %s", result)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("sync_analytics_snapshot failed: %s", exc)
        raise self.retry(exc=exc, countdown=120, max_retries=3)


# ─────────────────────────────────────────────────────────────────────────────
# Escalation notification
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.send_escalation_notification", bind=True)
def send_escalation_notification(
    self,
    escalation_id: str,
    escalation_data: dict[str, Any],
) -> dict[str, Any]:
    """Send email/webhook notification when a conversation is escalated."""
    try:
        from app.services.notification_service import send_escalation_email
        result = _run(send_escalation_email(escalation_id, escalation_data))
        logger.info("Escalation notification sent: %s", escalation_id)
        return {"sent": True, "escalation_id": escalation_id, **result}
    except Exception as exc:  # noqa: BLE001
        logger.error("send_escalation_notification failed: %s", exc)
        raise self.retry(exc=exc, countdown=30, max_retries=5)


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge-base document ingestion
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.ingest_document", bind=True)
def ingest_document(
    self,
    document_id: str,
    content: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Embed and store a document in the long-term vector memory (ChromaDB)."""
    try:
        async def _ingest():
            from app.memory.long_term import long_term_memory
            mem = long_term_memory()
            await mem.store(
                key=document_id,
                value=content,
                metadata=metadata,
            )
            return {"stored": True, "document_id": document_id}

        result = _run(_ingest())
        logger.info("Document ingested: %s", document_id)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("ingest_document failed doc=%s: %s", document_id, exc)
        raise self.retry(exc=exc, countdown=60, max_retries=3)


# ─────────────────────────────────────────────────────────────────────────────
# Chat session summary (triggered after session close)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.summarize_chat_session", bind=True)
def summarize_chat_session(
    self,
    session_id: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate and persist a conversation summary for a closed chat session."""
    try:
        if not messages:
            return {"summary": "", "session_id": session_id}

        conversation = "\n".join(
            f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
            for m in messages[-50:]  # last 50 messages
        )
        summary = f"[Auto-summary] Session {session_id}: {len(messages)} messages exchanged."

        async def _persist():
            from app.memory.short_term import short_term_memory
            redis = short_term_memory()
            if not redis._client:
                await redis.connect()
            await redis._client.setex(
                f"session:summary:{session_id}",
                86400,  # 24h
                summary,
            )

        _run(_persist())
        logger.info("Session summarised: %s", session_id)
        return {"summary": summary, "session_id": session_id}
    except Exception as exc:  # noqa: BLE001
        logger.error("summarize_chat_session failed: %s", exc)
        raise self.retry(exc=exc, countdown=60, max_retries=2)
