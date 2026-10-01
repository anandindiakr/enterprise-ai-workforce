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
        # LongTermMemory.upsert is synchronous — call directly
        from app.memory.long_term import long_term_memory
        mem = long_term_memory()
        mem.upsert(content, doc_id=document_id, metadata=metadata)

        # Update embedding_status in DB (requires async session)
        async def _update_status() -> None:
            import uuid as _uuid
            from sqlalchemy import update as _upd
            from app.db.models import KnowledgeDocumentModel
            from app.db.session import AsyncSessionLocal
            try:
                did = _uuid.UUID(document_id)
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        _upd(KnowledgeDocumentModel)
                        .where(KnowledgeDocumentModel.id == did)
                        .values(embedding_status="complete")
                    )
                    await db.commit()
            except Exception as db_exc:  # noqa: BLE001
                logger.warning("embedding_status update skipped: %s", db_exc)

        _run(_update_status())
        logger.info("Document ingested: %s", document_id)
        return {"stored": True, "document_id": document_id}
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


# ─────────────────────────────────────────────────────────────────────────────
# Workflow execution
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.execute_workflow", bind=True)
def execute_workflow(
    self,
    workflow_id: str,
    workflow_name: str,
    department: str,
    steps: list[dict[str, Any]],
    inputs: dict[str, Any],
    triggered_by: str,
) -> dict[str, Any]:
    """Execute a multi-step departmental workflow via the agent factory."""
    try:
        async def _exec():
            results: list[dict[str, Any]] = []
            for i, step in enumerate(steps or [], start=1):
                step_name  = step.get("name", f"Step {i}")
                step_agent = step.get("agent", department)
                step_task  = step.get("task", step.get("description", "Process workflow step"))
                try:
                    from app.agents.factory import build_department_agent
                    from app.core.types import Department
                    # Build the department agent and run it off-thread (agent.run
                    # is synchronous — same pattern as WorkforceRouter.execute).
                    agent = build_department_agent(Department(step_agent))
                    response = await asyncio.to_thread(
                        agent.run,
                        f"[Workflow: {workflow_name}] Step {i}/{len(steps)}: {step_task}\nInputs: {inputs}",
                    )
                    results.append({"step": step_name, "status": "success", "output": str(response)[:500]})
                except Exception as step_exc:  # noqa: BLE001
                    results.append({"step": step_name, "status": "error", "error": str(step_exc)})

            # Persist execution log to Redis
            from app.memory.short_term import short_term_memory
            redis = short_term_memory()
            if not redis._client:
                await redis.connect()
            import json
            await redis._client.setex(
                f"workflow:result:{self.request.id}",
                3600,
                json.dumps({"workflow_id": workflow_id, "steps": results, "triggered_by": triggered_by}),
            )
            return results

        results = _run(_exec())
        logger.info("Workflow %s completed (%d steps)", workflow_name, len(results))
        return {
            "task_id": self.request.id,
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "status": "completed",
            "results": results,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("execute_workflow failed %s: %s", workflow_id, exc)
        raise self.retry(exc=exc, countdown=30, max_retries=2)


@celery_app.task(name="app.workers.tasks.get_workflow_result", bind=True)
def get_workflow_result(self, task_id: str) -> dict[str, Any]:
    """Fetch workflow execution result from Redis cache."""
    try:
        async def _fetch():
            from app.memory.short_term import short_term_memory
            import json
            redis = short_term_memory()
            if not redis._client:
                await redis.connect()
            raw = await redis._client.get(f"workflow:result:{task_id}")
            return json.loads(raw) if raw else None

        return _run(_fetch()) or {"task_id": task_id, "status": "pending"}
    except Exception as exc:  # noqa: BLE001
        return {"task_id": task_id, "status": "error", "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# System health monitor — alerts the admin when a service goes down
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.check_system_health", bind=True)
def check_system_health(self) -> dict[str, Any]:
    """Every 2 minutes: probe each backing service; when one fails (or
    recovers), email the admin exactly once per incident.

    Recipients: ALERT_EMAIL env var if set, otherwise every active admin's
    email address. Alert state lives in Redis so restarts don't resend.
    """
    try:
        async def _check() -> dict[str, Any]:
            import redis.asyncio as aioredis

            from app.core.config import settings
            from app.db.session import AsyncSessionLocal
            from app.services.notification_service import send_generic_email

            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            results: dict[str, str] = {}

            # ── Probe each service ───────────────────────────────────────
            # PostgreSQL
            try:
                from sqlalchemy import text
                async with AsyncSessionLocal() as db:
                    await db.execute(text("SELECT 1"))
                results["postgresql"] = "healthy"
            except Exception as exc:  # noqa: BLE001
                results["postgresql"] = f"unhealthy: {exc}"

            # Redis (we're already talking to it — this covers the broker)
            try:
                await r.ping()
                results["redis"] = "healthy"
            except Exception as exc:  # noqa: BLE001
                results["redis"] = f"unhealthy: {exc}"

            # API service (this task runs in the worker — probe the API container)
            try:
                import aiohttp
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(
                        "http://api:8000/api/v1/health",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        results["api"] = "healthy" if resp.status == 200 else f"unhealthy: http {resp.status}"
            except Exception as exc:  # noqa: BLE001
                results["api"] = f"unhealthy: {exc}"

            # ── Compare with previous state, alert on transitions ────────
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            transitions: list[tuple[str, str, str]] = []  # (service, from, to)
            for svc, state in results.items():
                prev = await r.get(f"health:alert:{svc}")
                cur = "healthy" if state == "healthy" else "unhealthy"
                if prev is None:
                    # First run — only alert if something is already broken.
                    if cur == "unhealthy":
                        transitions.append((svc, "unknown", cur))
                elif prev != cur:
                    transitions.append((svc, prev, cur))
                await r.setex(f"health:alert:{svc}", 3600, cur)

            if transitions:
                # Resolve recipients
                to_addrs: list[str] = []
                if settings.alert_email:
                    to_addrs.append(settings.alert_email)
                else:
                    try:
                        async with AsyncSessionLocal() as db:
                            from sqlalchemy import select
                            from app.db.models import UserModel
                            rows = await db.execute(
                                select(UserModel.email).where(
                                    UserModel.is_active.is_(True),
                                    UserModel.roles.contains('["admin"]'),
                                )
                            )
                            to_addrs.extend(e for (e,) in rows if e and "@" in e)
                    except Exception:  # noqa: BLE001
                        pass

                lines = [f"Service status change detected at {now}:\n"]
                for svc, old, new in transitions:
                    tag = "RECOVERED" if new == "healthy" else "DOWN"
                    lines.append(f"- {svc}: {old} -> {new} [{tag}] — {results.get(svc, '')}")
                body = "\n".join(lines)
                subject = "[AI Workforce] Service " + ", ".join(
                    f"{svc} {'recovered' if new == 'healthy' else 'DOWN'}" for svc, _, new in transitions
                )

                for addr in dict.fromkeys(to_addrs):  # dedupe, preserve order
                    try:
                        await send_generic_email(addr, subject, body)
                        logger.info("Health alert emailed to %s: %s", addr, subject)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Health alert email to %s failed: %s", addr, exc)

            await r.aclose()
            return {"checked_at": now, "results": results, "transitions": len(transitions)}

        return _run(_check())
    except Exception as exc:  # noqa: BLE001
        logger.error("check_system_health failed: %s", exc)
        raise self.retry(exc=exc, countdown=60, max_retries=2)
