"""Authentication and RBAC primitives."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.models.schemas import Principal

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str,
    *,
    tenant_id: str | None = None,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    expires_minutes: int | None = None,
) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)``."""
    expire_minutes = expires_minutes or settings.jwt_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": roles or [],
        "scopes": scopes or [],
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": settings.app_name,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expire_minutes * 60


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AuthenticationError(f"Invalid token: {exc}") from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_principal(
    token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Header(default=None, alias=None),
) -> Principal:
    """Resolve the calling principal from JWT bearer or internal API key."""
    # Internal service-to-service path
    if api_key and api_key == settings.internal_api_key:
        return Principal(user_id="system", roles=["service"], scopes=["*"])

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
        )

    payload = decode_token(token)
    return Principal(
        user_id=payload.get("sub", "unknown"),
        tenant_id=payload.get("tenant_id"),
        roles=payload.get("roles", []),
        scopes=payload.get("scopes", []),
    )


def require_roles(*required: str):
    """Dependency factory enforcing that the principal owns *required* roles."""

    def _checker(principal: Principal = Depends(get_principal)) -> Principal:
        if not set(required).issubset(set(principal.roles)) and "service" not in principal.roles:
            raise AuthorizationError(f"Missing roles: {required}")
        return principal

    return _checker
