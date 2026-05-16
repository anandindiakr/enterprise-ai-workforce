"""User + chat session + message + escalation + audit data-access layer."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import bcrypt
from sqlalchemy import select, update, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    UserModel,
    ChatSessionModel,
    ChatMessageModel,
    EscalationModel,
    AuditLogModel,
    KnowledgeDocumentModel,
)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

async def get_user_by_username(db: AsyncSession, username: str) -> UserModel | None:
    result = await db.execute(select(UserModel).where(UserModel.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> UserModel | None:
    result = await db.execute(select(UserModel).where(UserModel.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> UserModel | None:
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    return result.scalar_one_or_none()


async def list_users(
    db: AsyncSession,
    tenant_id: str = "default",
    skip: int = 0,
    limit: int = 50,
) -> list[UserModel]:
    result = await db.execute(
        select(UserModel)
        .where(UserModel.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
        .order_by(UserModel.created_at.desc())
    )
    return list(result.scalars().all())


async def create_user(
    db: AsyncSession,
    *,
    username: str,
    email: str,
    password: str,
    full_name: str | None = None,
    tenant_id: str = "default",
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    is_superuser: bool = False,
) -> UserModel:
    user = UserModel(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        tenant_id=tenant_id,
        roles=roles or ["agent"],
        scopes=scopes or ["chat", "voice", "workflows"],
        is_superuser=is_superuser,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user: UserModel,
    *,
    full_name: str | None = None,
    email: str | None = None,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    is_active: bool | None = None,
) -> UserModel:
    if full_name is not None:
        user.full_name = full_name
    if email is not None:
        user.email = email
    if roles is not None:
        user.roles = roles
    if scopes is not None:
        user.scopes = scopes
    if is_active is not None:
        user.is_active = is_active
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user: UserModel, new_password: str) -> UserModel:
    user.hashed_password = hash_password(new_password)
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return user


async def delete_user(db: AsyncSession, user: UserModel) -> None:
    await db.delete(user)
    await db.flush()


async def touch_last_login(db: AsyncSession, user: UserModel) -> None:
    user.last_login = datetime.now(timezone.utc)
    await db.flush()


async def authenticate_user(db: AsyncSession, username: str, password: str) -> UserModel | None:
    user = await get_user_by_username(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    await touch_last_login(db, user)
    return user


# ---------------------------------------------------------------------------
# Chat Session CRUD
# ---------------------------------------------------------------------------

async def create_chat_session(
    db: AsyncSession,
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    tenant_id: str = "default",
    department: str = "reception",
    title: str | None = None,
    metadata: dict | None = None,
) -> ChatSessionModel:
    obj_id = uuid.UUID(session_id) if session_id else uuid.uuid4()
    uid = uuid.UUID(user_id) if user_id and user_id not in ("anonymous", "voice-user", "twilio-caller") else None
    session = ChatSessionModel(
        id=obj_id,
        user_id=uid,
        tenant_id=tenant_id,
        department=department,
        title=title or f"Chat – {department}",
        status="active",
        metadata_=metadata or {},
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def get_chat_session(db: AsyncSession, session_id: str) -> ChatSessionModel | None:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        return None
    result = await db.execute(select(ChatSessionModel).where(ChatSessionModel.id == sid))
    return result.scalar_one_or_none()


async def list_chat_sessions(
    db: AsyncSession,
    *,
    tenant_id: str = "default",
    user_id: str | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[ChatSessionModel]:
    q = select(ChatSessionModel).where(ChatSessionModel.tenant_id == tenant_id)
    if user_id:
        try:
            q = q.where(ChatSessionModel.user_id == uuid.UUID(user_id))
        except ValueError:
            pass
    if status:
        q = q.where(ChatSessionModel.status == status)
    q = q.order_by(ChatSessionModel.updated_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def close_chat_session(db: AsyncSession, session: ChatSessionModel) -> ChatSessionModel:
    session.status = "closed"
    session.closed_at = datetime.now(timezone.utc)
    await db.flush()
    return session


async def update_session_summary(
    db: AsyncSession, session: ChatSessionModel, summary: str
) -> ChatSessionModel:
    session.summary = summary
    await db.flush()
    return session


# ---------------------------------------------------------------------------
# Chat Message CRUD
# ---------------------------------------------------------------------------

async def add_chat_message(
    db: AsyncSession,
    *,
    session_id: str,
    role: str,
    content: str,
    department: str | None = None,
    agent_name: str | None = None,
    tokens_used: int = 0,
    metadata: dict | None = None,
) -> ChatMessageModel:
    msg = ChatMessageModel(
        session_id=uuid.UUID(session_id),
        role=role,
        content=content,
        department=department,
        agent_name=agent_name,
        tokens_used=tokens_used,
        metadata_=metadata or {},
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    return msg


async def list_chat_messages(
    db: AsyncSession,
    session_id: str,
    *,
    skip: int = 0,
    limit: int = 200,
) -> list[ChatMessageModel]:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        return []
    result = await db.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == sid)
        .order_by(ChatMessageModel.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Escalation CRUD
# ---------------------------------------------------------------------------

async def create_escalation(
    db: AsyncSession,
    *,
    session_id: str | None,
    tenant_id: str,
    user_id: str | None,
    department: str,
    reason: str,
    priority: str = "normal",
    metadata: dict | None = None,
) -> EscalationModel:
    sid = None
    if session_id:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            pass
    esc = EscalationModel(
        session_id=sid,
        tenant_id=tenant_id,
        user_id=user_id,
        department=department,
        reason=reason,
        priority=priority,
        status="open",
        metadata_=metadata or {},
    )
    db.add(esc)
    await db.flush()
    await db.refresh(esc)
    return esc


async def list_escalations(
    db: AsyncSession,
    *,
    tenant_id: str = "default",
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[EscalationModel]:
    q = select(EscalationModel).where(EscalationModel.tenant_id == tenant_id)
    if status:
        q = q.where(EscalationModel.status == status)
    q = q.order_by(EscalationModel.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def resolve_escalation(
    db: AsyncSession,
    escalation: EscalationModel,
    *,
    resolution_notes: str | None = None,
    assigned_to: str | None = None,
) -> EscalationModel:
    escalation.status = "resolved"
    escalation.resolved_at = datetime.now(timezone.utc)
    if resolution_notes:
        escalation.resolution_notes = resolution_notes
    if assigned_to:
        escalation.assigned_to = assigned_to
    await db.flush()
    return escalation


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

async def write_audit_log(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict | None = None,
) -> AuditLogModel:
    log = AuditLogModel(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details or {},
    )
    db.add(log)
    await db.flush()
    return log


async def list_audit_logs(
    db: AsyncSession,
    *,
    tenant_id: str = "default",
    user_id: str | None = None,
    action: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLogModel]:
    q = select(AuditLogModel).where(AuditLogModel.tenant_id == tenant_id)
    if user_id:
        q = q.where(AuditLogModel.user_id == user_id)
    if action:
        q = q.where(AuditLogModel.action == action)
    q = q.order_by(AuditLogModel.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Knowledge Document CRUD
# ---------------------------------------------------------------------------

async def create_knowledge_document(
    db: AsyncSession,
    *,
    tenant_id: str,
    title: str,
    category: str | None,
    content: str,
    file_name: str | None = None,
    file_size: int = 0,
    mime_type: str | None = None,
    uploaded_by: str | None = None,
    metadata: dict | None = None,
) -> KnowledgeDocumentModel:
    doc = KnowledgeDocumentModel(
        tenant_id=tenant_id,
        title=title,
        category=category,
        content=content,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type,
        uploaded_by=uploaded_by,
        embedding_status="pending",
        metadata_=metadata or {},
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc


async def list_knowledge_documents(
    db: AsyncSession,
    *,
    tenant_id: str = "default",
    category: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[KnowledgeDocumentModel]:
    q = select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.tenant_id == tenant_id)
    if category:
        q = q.where(KnowledgeDocumentModel.category == category)
    q = q.order_by(KnowledgeDocumentModel.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())
