"""Chat REST endpoints (standard + SSE streaming)."""

from __future__ import annotations

import json
import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, ChatResponse, Principal
from app.security.auth import optional_principal
from app.services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    principal: Principal = Depends(optional_principal),
) -> ChatResponse:
    """Single-turn chat. The platform infers department if none provided."""
    if request.tenant_id is None:
        request.tenant_id = principal.tenant_id
    if not request.user_id:
        request.user_id = principal.user_id
    return await chat_service().handle(request)


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    principal: Principal = Depends(optional_principal),
) -> StreamingResponse:
    """Server-Sent Events streaming endpoint.

    Emits a series of ``data: <json>\\n\\n`` events:
    - ``{"type": "typing"}`` – agent is thinking
    - ``{"type": "token",  "token": "<str>"}`` – incremental text token
    - ``{"type": "done",   "response": <ChatResponse JSON>}`` – final response
    - ``{"type": "error",  "message": "<str>"}`` – error
    """
    if request.tenant_id is None:
        request.tenant_id = principal.tenant_id
    if not request.user_id:
        request.user_id = principal.user_id

    async def event_generator() -> AsyncIterator[str]:
        # Announce typing immediately
        yield _sse({"type": "typing"})
        await asyncio.sleep(0)

        try:
            response: ChatResponse = await chat_service().handle(request)
            content: str = response.message.content or ""

            # Stream tokens: split on words for a natural feel
            words = content.split(" ")
            for i, word in enumerate(words):
                chunk = word + ("" if i == len(words) - 1 else " ")
                yield _sse({"type": "token", "token": chunk})
                await asyncio.sleep(0.02)  # 20 ms between tokens

            # Final event with full structured response
            yield _sse({"type": "done", "response": response.model_dump(mode="json")})

        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
