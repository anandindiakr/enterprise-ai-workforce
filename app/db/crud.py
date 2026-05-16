"""User data-access layer: create, read, update, delete."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserModel


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# CRUD
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
