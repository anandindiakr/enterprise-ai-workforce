"""Authentication and RBAC primitives."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.db.session import get_db
from app.models.schemas import Principal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def create_access_token(
    subject: str,
    *,
    tenant_id: str | None = None,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    is_superuser: bool = False,
    expires_minutes: int | None = None,
    expires_in: int | None = None,  # seconds override
    token_version: int | None = None,  # session-kill version — must match users.token_version
) -> str:
    """Return a signed JWT string."""
    if expires_in is not None:
        expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    else:
        expire_minutes = expires_minutes or settings.jwt_expire_minutes
        expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": roles or [],
        "scopes": scopes or [],
        "is_superuser": bool(is_superuser),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": settings.app_name,
    }
    if token_version is not None:
        payload["tv"] = token_version
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AuthenticationError(f"Invalid token: {exc}") from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def _validate_session_version(
    db: AsyncSession,
    payload: dict[str, Any],
    principal: Principal,
) -> Principal:
    """Reject tokens whose session was revoked (token_version bump) or whose
    account was deleted/disabled — regardless of the JWT's own expiry."""
    tv = payload.get("tv")
    if tv is None:
        return principal  # legacy token without a version claim — JWT expiry only
    try:
        from app.db.crud import get_user_by_username

        user = await get_user_by_username(db, payload.get("sub", ""))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists")
        if getattr(user, "token_version", 1) != int(tv):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "session_revoked", "message": "This session was signed out. Please log in again."})
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is disabled")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # DB briefly unavailable — fail open so a blip doesn't log everyone out.
        from loguru import logger
        logger.warning("session version check failed open: {}", exc)
    return principal


async def get_principal(
    token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Header(default=None, alias="x-api-key"),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    """Resolve the calling principal from JWT bearer or internal API key."""
    # Internal service-to-service path
    if api_key and api_key == settings.internal_api_key:
        return Principal(user_id="system", roles=["service"], scopes=["*"], is_superuser=True)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
        )

    payload = decode_token(token)
    principal = Principal(
        user_id=payload.get("sub", "unknown"),
        tenant_id=payload.get("tenant_id"),
        roles=payload.get("roles", []),
        scopes=payload.get("scopes", []),
        is_superuser=bool(payload.get("is_superuser", False)),
    )
    return await _validate_session_version(db, payload, principal)


async def optional_principal(
    token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Header(default=None, alias="x-api-key"),
) -> Principal:
    """Like get_principal but returns an anonymous principal when no credentials are provided."""
    if api_key and api_key == settings.internal_api_key:
        return Principal(user_id="system", roles=["service"], scopes=["*"], is_superuser=True)

    if token:
        try:
            payload = decode_token(token)
            return Principal(
                user_id=payload.get("sub", "anonymous"),
                tenant_id=payload.get("tenant_id"),
                roles=payload.get("roles", []),
                scopes=payload.get("scopes", []),
                is_superuser=bool(payload.get("is_superuser", False)),
            )
        except Exception:
            pass

    return Principal(user_id="anonymous", roles=["guest"], scopes=["chat:read", "chat:write"])


# Alias used by voice routes
get_optional_principal = optional_principal


def require_roles(*required: str):
    """Dependency factory enforcing that the principal owns *required* roles."""

    def _checker(principal: Principal = Depends(get_principal)) -> Principal:
        if not set(required).issubset(set(principal.roles)) and "service" not in principal.roles:
            raise AuthorizationError(f"Missing roles: {required}")
        return principal

    return _checker


async def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    """Dependency: caller must have the 'admin' role."""
    if "admin" not in principal.roles and "service" not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return principal


async def require_superuser(principal: Principal = Depends(get_principal)) -> Principal:
    """Dependency: caller must be the platform super-admin (or an internal service).

    Tenant-level admins have roles=['admin'] too, so the admin ROLE alone must
    never grant platform-wide power — only the is_superuser claim does.
    """
    if not principal.is_superuser and "service" not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access required",
        )
    return principal
