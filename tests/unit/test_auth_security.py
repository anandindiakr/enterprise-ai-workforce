"""Tests for failed-login lockout and token_version session invalidation."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routes import auth as auth_routes
from app.api.routes.auth import (
    LOGIN_MAX_FAILURES,
    _clear_login_failures,
    _lockout_remaining_seconds,
    _record_login_failure,
    login,
    logout_all_sessions,
)
from app.db import crud
from app.models.schemas import Principal, TokenRequest
from app.security.auth import create_access_token, get_principal


class _FakeRequest:
    client = None


class _FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *args, **kwargs):
        self.tasks.append((fn, args, kwargs))


@pytest.fixture(autouse=True)
def _reset_lockout_state():
    auth_routes._login_failures.clear()
    yield
    auth_routes._login_failures.clear()


@pytest.mark.asyncio
async def test_lockout_after_max_failures(db_session):
    user = await crud.create_user(
        db_session, username="bob", email="bob@example.com", password="correct123", roles=["agent"],
    )
    await db_session.commit()
    bt = _FakeBackgroundTasks()

    # N-1 failures → still 401
    for _ in range(LOGIN_MAX_FAILURES - 1):
        with pytest.raises(HTTPException) as exc:
            await login(_FakeRequest(), TokenRequest(username="bob", password="wrong"), bt, db=db_session)
        assert exc.value.status_code == 401

    assert _lockout_remaining_seconds("bob") == 0

    # Nth failure → locks the account
    with pytest.raises(HTTPException) as exc:
        await login(_FakeRequest(), TokenRequest(username="bob", password="wrong"), bt, db=db_session)
    assert exc.value.status_code == 401
    assert _lockout_remaining_seconds("bob") > 0

    # Even the CORRECT password is refused while locked (429)
    with pytest.raises(HTTPException) as exc:
        await login(_FakeRequest(), TokenRequest(username="bob", password="correct123"), bt, db=db_session)
    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "account_locked"

    # Audit entries were queued for each failed attempt
    assert len(bt.tasks) == LOGIN_MAX_FAILURES

    # Clearing failures (successful login path) restores access
    _clear_login_failures("bob")
    token = await login(_FakeRequest(), TokenRequest(username="bob", password="correct123"), bt, db=db_session)
    assert token.access_token


@pytest.mark.asyncio
async def test_token_version_invalidates_sessions(db_session):
    user = await crud.create_user(
        db_session, username="carol", email="carol@example.com", password="pw12345", roles=["admin"],
    )
    await db_session.commit()

    # Login → token carries current token_version
    token = await login(_FakeRequest(), TokenRequest(username="carol", password="pw12345"), _FakeBackgroundTasks(), db=db_session)
    principal = await get_principal(token=token.access_token, api_key=None, db=db_session)
    assert principal.user_id == "carol"

    # Sign Out Everywhere bumps token_version
    result = await logout_all_sessions(Principal(user_id="carol", roles=["admin"], scopes=[], is_superuser=False), db=db_session)
    assert "signed out" in result["message"].lower()

    # Old token is now dead — immediately, regardless of expiry
    with pytest.raises(HTTPException) as exc:
        await get_principal(token=token.access_token, api_key=None, db=db_session)
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "session_revoked"

    # Fresh login works and carries the bumped version
    token2 = await login(_FakeRequest(), TokenRequest(username="carol", password="pw12345"), _FakeBackgroundTasks(), db=db_session)
    principal2 = await get_principal(token=token2.access_token, api_key=None, db=db_session)
    assert principal2.user_id == "carol"


@pytest.mark.asyncio
async def test_password_change_bumps_token_version(db_session):
    user = await crud.create_user(
        db_session, username="dave", email="dave@example.com", password="oldpw123", roles=["agent"],
    )
    await db_session.commit()
    old_version = int(getattr(user, "token_version", 1))

    from app.api.routes.auth import ChangePasswordRequest, change_password
    await change_password(
        ChangePasswordRequest(current_password="oldpw123", new_password="newpw456"),
        principal=Principal(user_id="dave", roles=["agent"], scopes=[], is_superuser=False),
        db=db_session,
    )
    assert int(getattr(user, "token_version", 1)) == old_version + 1


def test_create_token_includes_tv_claim():
    import base64, json
    token = create_access_token("u1", token_version=7, expires_in=60)
    payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
    assert payload["tv"] == 7

    # Without tv → claim absent (backward compatible with old tokens)
    token2 = create_access_token("u1", expires_in=60)
    payload2 = json.loads(base64.urlsafe_b64decode(token2.split(".")[1] + "=="))
    assert "tv" not in payload2
