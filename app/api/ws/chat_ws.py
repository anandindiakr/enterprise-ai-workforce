"""WebSocket handler for real-time chat sessions."""

from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import logger
from app.models.schemas import ChatRequest
from app.services.chat_service import chat_service

router = APIRouter()


@router.websocket("/ws/chat")
@router.websocket("/ws/chat/{session_id}")
async def chat_socket(ws: WebSocket, session_id: str | None = None) -> None:
    """Bidirectional chat WebSocket.

    Inbound frames: ``{"message": str, "department"?: str, "metadata"?: {...}}``.
    Outbound frames: ChatResponse JSON.
    """
    await ws.accept()
    session_id = session_id or uuid4().hex
    user_id = ws.query_params.get("user_id", "anonymous")
    tenant_id = ws.query_params.get("tenant_id")

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
