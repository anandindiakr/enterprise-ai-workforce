"""Unit tests for admin user provisioning across tenants.

Verifies that the admin create-user endpoint honours tenant scoping:
- a platform (default-tenant) admin can provision a user into an existing tenant,
- a tenant-level admin cannot create users in another tenant (403),
- unknown target tenants are rejected (422),
- roles are sanitised to the known set.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routes.auth import AdminCreateUserRequest, create_user_admin
from app.db.models import TenantModel
from app.models.schemas import Principal


async def _add_tenant(db, slug: str) -> None:
    db.add(TenantModel(
        slug=slug,
        name=slug.title(),
        admin_email=f"admin@{slug}.com",
        plan="pro",
        max_users=50,
        max_chat_sessions=5000,
        max_voice_minutes=300,
    ))
    await db.commit()


def _principal(user_id: str, tenant_id: str) -> Principal:
    return Principal(user_id=user_id, tenant_id=tenant_id, roles=["admin"])


@pytest.mark.asyncio
async def test_platform_admin_provisions_user_into_tenant(db_session):
    await _add_tenant(db_session, "acme")

    user = await create_user_admin(
        AdminCreateUserRequest(
            username="bob",
            email="bob@acme.com",
            password="secret123",
            tenant_id="acme",
            roles=["admin"],
        ),
        principal=_principal("superadmin", "default"),
        db=db_session,
    )

    assert user.tenant_id == "acme"
    assert user.roles == ["admin"]
    assert user.is_active is True


@pytest.mark.asyncio
async def test_tenant_admin_cannot_create_user_in_other_tenant(db_session):
    await _add_tenant(db_session, "acme")
    await _add_tenant(db_session, "globex")

    with pytest.raises(HTTPException) as excinfo:
        await create_user_admin(
            AdminCreateUserRequest(
                username="carol",
                email="carol@globex.com",
                password="secret123",
                tenant_id="globex",
            ),
            principal=_principal("acmeadmin", "acme"),
            db=db_session,
        )
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_unknown_target_tenant_rejected(db_session):
    with pytest.raises(HTTPException) as excinfo:
        await create_user_admin(
            AdminCreateUserRequest(
                username="dave",
                email="dave@nowhere.com",
                password="secret123",
                tenant_id="ghost",
            ),
            principal=_principal("superadmin", "default"),
            db=db_session,
        )
    assert excinfo.value.status_code == 422


@pytest.mark.asyncio
async def test_roles_sanitised_to_known_set(db_session):
    user = await create_user_admin(
        AdminCreateUserRequest(
            username="eve",
            email="eve@default.com",
            password="secret123",
            roles=["superadmin", "root", "user"],
        ),
        principal=_principal("superadmin", "default"),
        db=db_session,
    )
    assert user.roles == ["user"]
    assert user.tenant_id == "default"


@pytest.mark.asyncio
async def test_is_active_honoured_on_create(db_session):
    user = await create_user_admin(
        AdminCreateUserRequest(
            username="frank",
            email="frank@default.com",
            password="secret123",
            is_active=False,
        ),
        principal=_principal("superadmin", "default"),
        db=db_session,
    )
    assert user.is_active is False


# ---------------------------------------------------------------------------
# Platform-superuser security gate (tenant management is superuser-only)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_superuser_blocks_tenant_admin():
    """A tenant-level admin (roles=['admin']) must NOT pass the platform gate."""
    from app.security.auth import require_superuser

    with pytest.raises(HTTPException) as excinfo:
        await require_superuser(principal=Principal(user_id="acmeadmin", roles=["admin"], is_superuser=False))
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_require_superuser_allows_superadmin_and_service():
    from app.security.auth import require_superuser

    ok = await require_superuser(principal=Principal(user_id="admin", roles=["admin"], is_superuser=True))
    assert ok.is_superuser is True
    svc = await require_superuser(principal=Principal(user_id="system", roles=["service"]))
    assert svc.user_id == "system"


def test_superuser_claim_survives_token_roundtrip():
    """The JWT must carry the is_superuser claim so the API can tell the
    platform super-admin apart from tenant admins."""
    from app.security.auth import create_access_token, decode_token

    super_tok = create_access_token(
        "admin", roles=["admin"], scopes=[], is_superuser=True, expires_in=120
    )
    assert decode_token(super_tok)["is_superuser"] is True

    tenant_tok = create_access_token(
        "acmeadmin", tenant_id="acme", roles=["admin"], scopes=[],
        is_superuser=False, expires_in=120,
    )
    assert decode_token(tenant_tok)["is_superuser"] is False
