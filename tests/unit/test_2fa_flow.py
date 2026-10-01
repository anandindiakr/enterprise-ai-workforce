"""Smoke test for the full TOTP 2FA flow: setup → enable → login gating.

Run: python -m pytest tests/unit/test_2fa_flow.py -q
"""
from __future__ import annotations

import pytest

import pyotp

from app.api.routes.auth import (
    login,
    twofa_disable,
    twofa_enable,
    twofa_setup,
    twofa_status,
)
from app.db import crud
from app.models.schemas import Principal, TokenRequest
from app.security.auth import create_access_token


def _principal(user) -> Principal:
    return Principal(
        user_id=user.username,
        tenant_id=user.tenant_id,
        roles=user.roles,
        scopes=user.scopes,
        is_superuser=user.is_superuser,
    )


class _FakeRequest:
    pass


@pytest.mark.asyncio
async def test_2fa_full_flow(db_session, monkeypatch):
    # ── Seed a user ────────────────────────────────────────────────
    user = await crud.create_user(
        db_session, username="alice", email="alice@example.com",
        password="secret123", roles=["agent"],
    )
    await db_session.commit()

    # ── Status is off initially ────────────────────────────────────
    status = await twofa_status(_principal(user), db=db_session)
    assert status == {"enabled": False}

    # ── Setup generates secret + QR ────────────────────────────────
    setup = await twofa_setup(_principal(user), db=db_session)
    assert setup["secret"] and setup["otpauth_url"].startswith("otpauth://")
    assert setup["qr_png"].startswith("data:image/png;base64,")

    # ── Login before enabling → NOT gated (secret exists but disabled)
    token = await login(
        _FakeRequest(),
        TokenRequest(username="alice", password="secret123"),
        db=db_session,
    )
    assert token.access_token

    # ── Enable with a valid code ───────────────────────────────────
    code = pyotp.TOTP(setup["secret"]).now()
    from app.api.routes.auth import TwoFAEnableRequest, TwoFADisableRequest
    result = await twofa_enable(
        TwoFAEnableRequest(code=code), principal=_principal(user), db=db_session
    )
    assert result["enabled"] is True

    # ── Status now on ──────────────────────────────────────────────
    status = await twofa_status(_principal(user), db=db_session)
    assert status == {"enabled": True}

    # ── Login WITHOUT code → 401 2fa_required ──────────────────────
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await login(
            _FakeRequest(),
            TokenRequest(username="alice", password="secret123"),
            db=db_session,
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "2fa_required"

    # ── Login with WRONG code → 401 2fa_invalid ────────────────────
    with pytest.raises(HTTPException) as exc_info:
        await login(
            _FakeRequest(),
            TokenRequest(username="alice", password="secret123", totp_code="000000"),
            db=db_session,
        )
    assert exc_info.value.detail["code"] == "2fa_invalid"

    # ── Login with correct code → succeeds ─────────────────────────
    code = pyotp.TOTP(setup["secret"]).now()
    token = await login(
        _FakeRequest(),
        TokenRequest(username="alice", password="secret123", totp_code=code),
        db=db_session,
    )
    assert token.access_token

    # ── Wrong password still rejected even with valid code ─────────
    with pytest.raises(HTTPException):
        await login(
            _FakeRequest(),
            TokenRequest(username="alice", password="wrongpass", totp_code=code),
            db=db_session,
        )

    # ── Disable with password + code ───────────────────────────────
    code = pyotp.TOTP(setup["secret"]).now()
    result = await twofa_disable(
        TwoFADisableRequest(password="secret123", code=code),
        principal=_principal(user), db=db_session,
    )
    assert result["enabled"] is False

    # ── Login works again without code ─────────────────────────────
    token = await login(
        _FakeRequest(),
        TokenRequest(username="alice", password="secret123"),
        db=db_session,
    )
    assert token.access_token
