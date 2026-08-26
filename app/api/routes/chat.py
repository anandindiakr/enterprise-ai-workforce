"""Chat REST endpoints: messaging, session history, CSV/JSON export."""

from __future__ import annotations

import csv
import io
import json
import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.db.crud import (
    create_chat_session,
    get_chat_session,
    list_chat_sessions,
    list_chat_messages,
    add_chat_message,
    close_chat_session,
    write_audit_log,
)
from app.db.session import get_db
from app.models.schemas import ChatRequest, ChatResponse, Principal
from app.security.auth import get_principal, optional_principal
from app.services.chat_service import chat_service, stream_chat_tokens

router = APIRouter(prefix="/chat", tags=["chat"])


async def _get_owned_session(
    db,
    session_id: str,
    tenant_id: str | None,
):
    """Fetch a chat session and enforce tenant ownership.

    A session that exists but belongs to another tenant is treated the same
    as a missing one (404) so session ids are never revealed across tenants.
    """
    session = await get_chat_session(db, session_id)
    if session is None or session.tenant_id != (tenant_id or "default"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


# ─────────────────────────────────────────────────────────────────────────────
# Send a message (single-turn)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse)
@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
    fast: bool = Query(False, description="Use the low-latency single-call path (voice)"),
    principal: Principal = Depends(optional_principal),
    db=Depends(get_db),
) -> ChatResponse:
    """Single-turn chat. The platform infers department if none provided.

    When ``fast=1`` the request is served by the low-latency handler tuned for
    voice (deterministic transfers + a single LLM call) instead of the full
    Swarms hierarchy.
    """
    # The authenticated tenant is authoritative: a client-supplied tenant_id is
    # only honoured for anonymous requests, so a logged-in user can never read
    # or write another tenant's data by spoofing the request body.
    request.tenant_id = principal.tenant_id or request.tenant_id or "default"
    if not request.user_id:
        request.user_id = principal.user_id

    # Ensure session exists in DB
    session_id = request.session_id or ""
    if session_id:
        existing = await get_chat_session(db, session_id)
        if existing is None:
            await create_chat_session(
                db,
                session_id=session_id,
                user_id=request.user_id,
                tenant_id=request.tenant_id,
                department=request.department or "reception",
            )
        elif existing.tenant_id != request.tenant_id:
            # Cross-tenant session id — never touch or acknowledge it.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    response = await (
        chat_service().handle_fast(request) if fast else chat_service().handle(request)
    )

    # Persist messages
    if session_id:
        try:
            await add_chat_message(
                db,
                session_id=session_id,
                role="user",
                content=request.message,
                department=request.department,
            )
            await add_chat_message(
                db,
                session_id=session_id,
                role="assistant",
                content=response.message.content or "",
                department=response.department,
                agent_name=response.agent_name,
            )
        except Exception:  # noqa: BLE001
            pass  # never break chat for persistence errors

    # Audit log
    try:
        await write_audit_log(
            db,
            tenant_id=request.tenant_id or "default",
            user_id=request.user_id,
            action="chat.message",
            resource_type="chat_session",
            resource_id=session_id or None,
            ip_address=req.client.host if req.client else None,
            details={"department": request.department, "message_length": len(request.message)},
        )
    except Exception:  # noqa: BLE001
        pass

    return response


# ─────────────────────────────────────────────────────────────────────────────
# SSE streaming
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    principal: Principal = Depends(optional_principal),
) -> StreamingResponse:
    """Server-Sent Events streaming endpoint."""
    # Authenticated tenant wins over any tenant_id in the request body (see
    # the single-turn handler for the same rationale).
    request.tenant_id = principal.tenant_id or request.tenant_id or "default"
    if not request.user_id:
        request.user_id = principal.user_id

    async def event_generator() -> AsyncIterator[str]:
        yield _sse({"type": "typing"})
        await asyncio.sleep(0)
        try:
            # Deterministic transfer handling: if the user explicitly asks to be
            # transferred, route through the full handler so the response carries
            # ``transferred_to`` and a clean handoff phrase (the raw token stream
            # cannot express a transfer). Same for topic-routing at the front
            # desk: when the console is pinned to Reception but the message
            # clearly belongs to another department, the full handler performs
            # the handoff instead of a generic "I don't have access" stream.
            from app.voice.session import detect_transfer_intent
            from app.swarms.router import workforce_router

            intent = detect_transfer_intent(request.message)
            pinned = request.department
            pinned_value = pinned.value if hasattr(pinned, "value") else pinned
            topic_dept = workforce_router().choose_department(request.message)
            needs_full_handler = (
                (intent is not None and intent != pinned)
                or (
                    pinned_value == "reception"
                    and topic_dept is not None
                    and topic_dept != pinned
                )
            )
            if needs_full_handler:
                resp = await chat_service().handle(request)
                content = resp.message.content or ""
                yield _sse({"type": "token", "token": content})
                transferred = (
                    resp.transferred_to.value
                    if hasattr(resp.transferred_to, "value")
                    else resp.transferred_to
                )
                yield _sse({
                    "type": "done",
                    "response": {"message": {"content": content}},
                    "transferred_to": transferred,
                })
                return

            full_text = ""
            async for token in stream_chat_tokens(request):
                full_text += token
                yield _sse({"type": "token", "token": token})
            yield _sse({"type": "done", "response": {"message": {"content": full_text}}})
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Session history
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    tenant_id: str = Query("default"),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """List chat sessions for the calling principal's tenant."""
    effective_tenant = principal.tenant_id or tenant_id
    sessions = await list_chat_sessions(
        db,
        tenant_id=effective_tenant,
        user_id=principal.user_id if "admin" not in principal.roles else None,
        status=status,
        skip=skip,
        limit=limit,
    )
    return {
        "sessions": [
            {
                "id": str(s.id),
                "department": s.department,
                "title": s.title,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in sessions
        ],
        "total": len(sessions),
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Get session metadata + message history (tenant-scoped)."""
    session = await _get_owned_session(db, session_id, principal.tenant_id)

    messages = await list_chat_messages(db, session_id, limit=500)
    return {
        "id": str(session.id),
        "department": session.department,
        "title": session.title,
        "status": session.status,
        "summary": session.summary,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "department": m.department,
                "agent_name": m.agent_name,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.delete("/sessions/{session_id}")
async def close_session(
    session_id: str,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Close / archive a chat session (tenant-scoped)."""
    session = await _get_owned_session(db, session_id, principal.tenant_id)
    await close_chat_session(db, session)
    return {"closed": True, "session_id": session_id}


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = Query("json", regex="^(json|csv)$"),
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> StreamingResponse:
    """Export a session's message history as JSON or CSV (tenant-scoped)."""
    session = await _get_owned_session(db, session_id, principal.tenant_id)
    messages = await list_chat_messages(db, session_id, limit=2000)

    if format == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["id", "role", "content", "department", "agent_name", "created_at"],
        )
        writer.writeheader()
        for m in messages:
            writer.writerow({
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "department": m.department or "",
                "agent_name": m.agent_name or "",
                "created_at": m.created_at.isoformat(),
            })
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="session_{session_id}.csv"'},
        )

    # JSON export
    data = {
        "session_id": session_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "department": session.department,
        "status": session.status,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "department": m.department,
                "agent_name": m.agent_name,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }
    return StreamingResponse(
        iter([json.dumps(data, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="session_{session_id}.json"'},
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# File upload (attach files to a chat context)
# ─────────────────────────────────────────────────────────────────────────────

_ALLOWED_MIME = {
    "text/plain", "text/csv", "text/markdown",
    "application/json", "application/pdf",
    "image/png", "image/jpeg", "image/gif", "image/webp",
}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str | None = Query(None),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Upload a file to attach to a chat session context.

    Returns a ``file_id`` reference that can be included in subsequent
    ``ChatRequest.file_ids`` to give the agent access to the file content.
    """
    import base64
    import uuid as _uuid

    content_type = file.content_type or "application/octet-stream"
    if content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{content_type}'. Allowed: {sorted(_ALLOWED_MIME)}",
        )

    raw = await file.read()
    if len(raw) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max 10 MB, got {len(raw)} bytes)")

    file_id  = str(_uuid.uuid4())
    is_image = content_type.startswith("image/")

    # Store in Redis for 30 minutes so the chat handler can pull it
    try:
        from app.memory.short_term import short_term_memory
        redis_mem = short_term_memory()
        if not redis_mem._client:
            await redis_mem.connect()
        payload = json.dumps({
            "file_id":      file_id,
            "filename":     file.filename or "upload",
            "content_type": content_type,
            "size":         len(raw),
            "session_id":   session_id,
            "user_id":      principal.user_id,
            "data_b64":     base64.b64encode(raw).decode() if is_image else None,
            "text":         raw.decode("utf-8", errors="replace") if not is_image else None,
        })
        await redis_mem._client.setex(f"upload:{file_id}", 1800, payload)
    except Exception:  # noqa: BLE001
        pass  # If Redis is unavailable, still return file_id — chat handler will degrade gracefully

    return {
        "file_id":      file_id,
        "filename":     file.filename,
        "content_type": content_type,
        "size_bytes":   len(raw),
        "session_id":   session_id,
        "expires_in":   1800,
    }
