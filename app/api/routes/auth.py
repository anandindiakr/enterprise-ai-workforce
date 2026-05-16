"""Authentication & user-management endpoints."""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db import crud
from app.db.models import UserModel
from app.models.schemas import Principal, TokenRequest, TokenResponse
from app.security.auth import create_access_token, get_principal, require_admin

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str | None = None

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username may only contain letters, digits, _ and -")
        return v


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str | None
    roles: list[str]
    scopes: list[str]
    is_active: bool
    is_superuser: bool
    tenant_id: str
    created_at: datetime
    last_login: datetime | None

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    roles: list[str] | None = None
    scopes: list[str] | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str | None) -> str | None:
        if v is not None and not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


# ── Auth endpoints ────────────────────────────────────────────────────────────

@router.post("/token", response_model=TokenResponse)
async def login(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await crud.authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    expires_in = 3600
    token = create_access_token(
        subject=user.username,
        roles=user.roles,
        scopes=user.scopes,
        tenant_id=user.tenant_id,
        expires_in=expires_in,
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=Principal)
async def me(principal: Principal = Depends(get_principal)) -> Principal:
    return principal


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Self-service registration (open by default; restrict in production)."""
    if await crud.get_user_by_username(db, payload.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if await crud.get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = await crud.create_user(
        db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    await db.commit()
    return UserResponse.model_validate(user)


@router.post("/change-password", status_code=200)
async def change_password(
    payload: ChangePasswordRequest,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await crud.get_user_by_username(db, principal.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not crud.verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await crud.change_password(db, user, payload.new_password)
    await db.commit()
    return {"message": "Password updated successfully"}


# ── User management (admin) ───────────────────────────────────────────────────

@router.patch("/profile", response_model=UserResponse, summary="Update own profile")
async def update_own_profile(
    payload: UpdateUserRequest,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Any authenticated user can update their own full_name and email."""
    user = await crud.get_user_by_username(db, principal.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = await crud.update_user(
        db, user,
        full_name=payload.full_name,
        email=payload.email,
    )
    await db.commit()
    return UserResponse.model_validate(user)


@users_router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    principal: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    users = await crud.list_users(db, tenant_id=principal.tenant_id, skip=skip, limit=limit)
    return [UserResponse.model_validate(u) for u in users]


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    principal: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@users_router.post("/", response_model=UserResponse, status_code=201)
async def create_user_admin(
    payload: RegisterRequest,
    principal: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    if await crud.get_user_by_username(db, payload.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if await crud.get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = await crud.create_user(
        db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    await db.commit()
    return UserResponse.model_validate(user)


@users_router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    principal: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = await crud.update_user(
        db, user,
        full_name=payload.full_name,
        email=payload.email,
        roles=payload.roles,
        scopes=payload.scopes,
        is_active=payload.is_active,
    )
    await db.commit()
    return UserResponse.model_validate(user)


@users_router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    principal: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(user.username) == principal.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    await crud.delete_user(db, user)
    await db.commit()
