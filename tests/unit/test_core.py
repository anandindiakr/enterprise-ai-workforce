"""Unit tests for authentication, CRUD helpers, and API routes.

Run with:
    pytest tests/unit/ -q --tb=short
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

class TestCreateDecodeToken:
    def test_roundtrip(self):
        from app.security.auth import create_access_token, decode_token
        # create_access_token(subject: str, *, tenant_id, roles, scopes, ...)
        token = create_access_token("alice", tenant_id="acme")
        claims = decode_token(token)
        assert claims["sub"] == "alice"
        assert claims.get("tenant_id") == "acme"

    def test_expired_raises(self):
        from jose import jwt
        from app.core.config import settings
        from app.core.exceptions import AuthenticationError
        from app.security.auth import decode_token
        expired = jwt.encode(
            {"sub": "alice", "exp": 1},  # epoch 1 = ancient past
            settings.jwt_secret,
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError):
            decode_token(expired)

    def test_bad_token_raises(self):
        from app.core.exceptions import AuthenticationError
        from app.security.auth import decode_token
        with pytest.raises(AuthenticationError):
            decode_token("not.a.valid.jwt")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHelpers:
    def test_hash_and_verify(self):
        from app.db.crud import hash_password, verify_password
        hashed = hash_password("secret123")
        assert hashed != "secret123"
        assert verify_password("secret123", hashed)
        assert not verify_password("wrong", hashed)


# ---------------------------------------------------------------------------
# Chat CRUD helpers (async, using an in-memory SQLite engine)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUserCRUD:
    async def test_create_and_get_user(self, db_session):
        from app.db.crud import create_user, get_user_by_username
        user = await create_user(
            db_session,
            username="bob",
            email="bob@acme.com",
            password="pass123",
            tenant_id="acme",
        )
        assert user.id is not None
        fetched = await get_user_by_username(db_session, "bob")
        assert fetched is not None
        assert fetched.email == "bob@acme.com"

    async def test_authenticate_user(self, db_session):
        from app.db.crud import create_user, authenticate_user
        await create_user(db_session, username="carol", email="c@c.com", password="mypass")
        auth = await authenticate_user(db_session, "carol", "mypass")
        assert auth is not None
        no_auth = await authenticate_user(db_session, "carol", "wrongpass")
        assert no_auth is None

    async def test_create_user_no_duplicate(self, db_session):
        from app.db.crud import create_user
        import sqlalchemy.exc
        await create_user(db_session, username="dave", email="d@d.com", password="x")
        with pytest.raises(Exception):  # IntegrityError or similar
            await create_user(db_session, username="dave", email="d2@d.com", password="x")


@pytest.mark.asyncio
class TestChatSessionCRUD:
    async def test_create_and_list(self, db_session):
        from app.db.crud import create_chat_session, list_chat_sessions
        session = await create_chat_session(
            db_session,
            tenant_id="acme",
            department="sales",
        )
        assert session.id is not None
        sessions = await list_chat_sessions(db_session, tenant_id="acme")
        assert len(sessions) >= 1

    async def test_add_and_list_messages(self, db_session):
        from app.db.crud import create_chat_session, add_chat_message, list_chat_messages
        session = await create_chat_session(db_session, tenant_id="t1")
        sid = str(session.id)
        await add_chat_message(db_session, session_id=sid, role="user", content="Hello")
        await add_chat_message(db_session, session_id=sid, role="assistant", content="Hi there")
        msgs = await list_chat_messages(db_session, sid)
        assert len(msgs) == 2
        assert msgs[0].role == "user"

    async def test_close_session(self, db_session):
        from app.db.crud import create_chat_session, close_chat_session, get_chat_session
        session = await create_chat_session(db_session, tenant_id="t1")
        await close_chat_session(db_session, session)
        refreshed = await get_chat_session(db_session, str(session.id))
        assert refreshed.status == "closed"


@pytest.mark.asyncio
class TestEscalationCRUD:
    async def test_create_and_resolve(self, db_session):
        from app.db.crud import create_escalation, list_escalations, resolve_escalation
        esc = await create_escalation(
            db_session,
            session_id=None,
            tenant_id="acme",
            user_id="user-1",
            department="hr",
            reason="Sensitive request",
            priority="high",
        )
        assert esc.status == "open"
        escs = await list_escalations(db_session, tenant_id="acme")
        assert len(escs) >= 1

        resolved = await resolve_escalation(
            db_session, esc, resolution_notes="Handled by HR manager"
        )
        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None


# ---------------------------------------------------------------------------
# Knowledge document CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestKnowledgeDocumentCRUD:
    async def test_create_and_list(self, db_session):
        from app.db.crud import create_knowledge_document, list_knowledge_documents
        doc = await create_knowledge_document(
            db_session,
            tenant_id="acme",
            title="IT Policy",
            category="IT",
            content="Use strong passwords.",
        )
        assert doc.embedding_status == "pending"
        docs = await list_knowledge_documents(db_session, tenant_id="acme")
        assert any(d.title == "IT Policy" for d in docs)


# ---------------------------------------------------------------------------
# Config smoke test
# ---------------------------------------------------------------------------

class TestConfig:
    def test_defaults_exist(self):
        from app.core.config import settings
        assert settings.app_name
        assert settings.jwt_secret
        assert settings.mcp_base_url

    def test_upload_dir_field(self):
        from app.core.config import settings
        assert hasattr(settings, "upload_dir")
        assert hasattr(settings, "max_upload_size_mb")


# ---------------------------------------------------------------------------
# Notification service (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestNotificationService:
    async def test_skips_when_no_recipient(self):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.escalation_email_to = ""
            mock_settings.resend_api_key = ""
            mock_settings.smtp_host = ""
            from app.services.notification_service import send_escalation_email
            result = await send_escalation_email("esc-123", {"reason": "test"})
        assert result["sent"] is False
