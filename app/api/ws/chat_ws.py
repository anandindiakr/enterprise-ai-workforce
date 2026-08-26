"""WebSocket handler for real-time chat sessions."""

from __future__ import annotations

import json
from uuid import uuid4

import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import logger
from app.core.exceptions import AuthenticationError
from app.security.auth import decode_token
from app.models.schemas import ChatRequest
from app.services.chat_service import chat_service

router = APIRouter()


@router.websocket("/ws/chat")
@router.websocket("/ws/chat/{session_id}")
async def chat_socket(ws: WebSocket, session_id: str | None = None) -> None:
    """Bidirectional chat WebSocket.

    Auth: optional JWT via ``?token=<jwt>`` query param.
    In production set ``REQUIRE_WS_AUTH=true`` to enforce auth.

    Inbound frames: ``{"message": str, "department"?: str, "metadata"?: {...}}``.
    Outbound frames: ChatResponse JSON.
    """
    # ── JWT auth (optional in dev, enforced in prod) ───────────────────────
    token = ws.query_params.get("token")
    principal_id = "anonymous"
    principal_tenant: str | None = None
    if token:
        try:
            claims = decode_token(token)
            principal_id = claims.get("sub", "anonymous")
            principal_tenant = claims.get("tenant_id")
        except AuthenticationError as exc:
            await ws.close(code=4001)
            logger.warning("Chat WS auth rejected: {}", exc)
            return
    elif os.getenv("REQUIRE_WS_AUTH", "").lower() == "true":
        await ws.close(code=4001)
        return

    await ws.accept()
    session_id = session_id or uuid4().hex
    user_id   = principal_id or ws.query_params.get("user_id", "anonymous")
    tenant_id = principal_tenant or ws.query_params.get("tenant_id")

    # Tenant ownership guard: a session id that exists in the DB but belongs
    # to another tenant must not be usable over the socket — otherwise a user
    # could read another tenant's transcript by guessing a session id.
    if principal_tenant and session_id:
        try:
            from app.db.crud import get_chat_session
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as _db:
                existing = await get_chat_session(_db, session_id)
                if existing is not None and existing.tenant_id != principal_tenant:
                    await ws.close(code=4001)
                    return
        except Exception:  # noqa: BLE001
            logger.debug("Chat WS tenant check skipped session={}", session_id)

    logger.info("Chat WS connected session={} user={}", session_id, user_id)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except Exception:
                await ws.send_json({"error": "invalid_json"})
                continue

            req = ChatRequest(
                session_id=session_id,
                user_id=user_id,
                tenant_id=tenant_id,
                message=payload.get("message", ""),
                department=payload.get("department"),
                metadata=payload.get("metadata", {}),
                streaming=True,
            )
            response = await chat_service().handle(req)
            await ws.send_json(response.model_dump(mode="json"))
    except WebSocketDisconnect:
        logger.info("Chat WS disconnected session={}", session_id)
