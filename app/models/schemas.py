"""Public Pydantic schemas (chat, voice, agents, workflows)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import Channel, Department, EscalationLevel, Role, SwarmStrategy


# ---------------------------------------------------------------------------
# Conversation primitives
# ---------------------------------------------------------------------------


class Attachment(BaseModel):
    """File or media attachment carried inside a message."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    mime_type: str
    size_bytes: int = 0
    url: str | None = None
    content_b64: str | None = None


class Message(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    session_id: str
    role: Role
    content: str
    department: Department | None = None
    agent_name: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    session_id: str | None = None
    user_id: str = "anonymous"
    tenant_id: str | None = None
    department: Department | None = None
    message: str
    attachments: list[Attachment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    streaming: bool = False


class ChatResponse(BaseModel):
    session_id: str
    message: Message
    agent_name: str
    department: Department
    escalation: EscalationLevel = EscalationLevel.NONE
    transferred_to: Department | None = None
    tool_calls: list["ToolCall"] = Field(default_factory=list)
    summary: str | None = None


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any | None = None
    duration_ms: int | None = None
    success: bool = True


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------


class VoiceSessionStartRequest(BaseModel):
    user_id: str | None = None
    tenant_id: str | None = None
    department: Department | None = None
    language: str = "en"
    sample_rate: int = 16000
    encoding: Literal["pcm16", "mulaw", "opus"] = "pcm16"
    metadata: dict[str, Any] = Field(default_factory=dict)


class VoiceSessionDescriptor(BaseModel):
    session_id: str
    department: Department
    language: str
    realtime_provider: str
    stt_provider: str
    tts_provider: str
    websocket_url: str
    expires_at: datetime


class TranscriptEvent(BaseModel):
    session_id: str
    text: str
    is_final: bool
    confidence: float | None = None
    language: str | None = None
    speaker: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class VoiceTurn(BaseModel):
    session_id: str
    user_text: str
    agent_text: str
    audio_url: str | None = None
    duration_ms: int | None = None
    department: Department


# ---------------------------------------------------------------------------
# Sessions / context
# ---------------------------------------------------------------------------


class SessionContext(BaseModel):
    session_id: str
    user_id: str
    tenant_id: str | None = None
    channel: Channel
    department: Department
    language: str = "en"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
    history: list[Message] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agents / orchestration
# ---------------------------------------------------------------------------


class AgentDescriptor(BaseModel):
    agent_name: str
    department: Department
    description: str
    model: str
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    voice_enabled: bool = True
    chat_enabled: bool = True


class WorkflowRequest(BaseModel):
    task: str
    department: Department | None = None
    strategy: SwarmStrategy | None = None
    user_id: str
    tenant_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    workflow_id: UUID = Field(default_factory=uuid4)
    department: Department
    strategy: SwarmStrategy
    output: Any
    duration_ms: int
    agents_involved: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    succeeded: bool = True
    error: str | None = None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TokenRequest(BaseModel):
    username: str
    password: str
    tenant_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class Principal(BaseModel):
    user_id: str
    tenant_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)


ChatResponse.model_rebuild()
