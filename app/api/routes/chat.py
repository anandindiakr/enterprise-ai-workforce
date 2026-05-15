"""Chat REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

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
