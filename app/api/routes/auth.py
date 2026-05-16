"""Authentication endpoints (token issue)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import Principal, TokenRequest, TokenResponse
from app.security.auth import create_access_token, get_principal

router = APIRouter(prefix="/auth", tags=["auth"])


# NOTE: In production replace this with a real user store + password verification.
# This stub demonstrates the intended shape. Integrate against your IdP / SSO.
_DEMO_USERS: dict[str, dict] = {
    "admin": {"password": "admin", "roles": ["admin", "agent"], "tenant": "default"},
    "agent": {"password": "agent", "roles": ["agent"], "tenant": "default"},
}


@router.post("/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest) -> TokenResponse:
    user = _DEMO_USERS.get(payload.username)
    if not user or user["password"] != payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    token, expires_in = create_access_token(
        subject=payload.username,
        tenant_id=payload.tenant_id or user["tenant"],
        roles=user["roles"],
        scopes=["chat", "voice", "workflows"],
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=Principal)
async def me(principal: Principal = Depends(get_principal)) -> Principal:
    return principal
