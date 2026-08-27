"""Unit tests for friendly conversation exports (TXT + PDF).

Covers the /chat/sessions/{id}/export endpoint's readable formats:
- txt returns a plain-text transcript with speaker labels and timestamps,
- pdf returns a real PDF (fpdf2) that starts with the %PDF magic,
- both are tenant-scoped (another tenant's session is 404).
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

# Same heavy-dep stubs as test_chat_routing.py — the chat route imports the
# chat service, which pulls in Docker-image-only packages at import time.
_swarms = types.ModuleType("swarms")
_swarms.SwarmRouter = MagicMock()
_swarms.Agent = MagicMock()
_swarms.HierarchicalSwarm = MagicMock()
sys.modules["swarms"] = _swarms

_factory = types.ModuleType("app.agents.factory")
_factory.build_all_department_agents = MagicMock(return_value={})
_factory.build_department_agent = MagicMock()
_factory.build_director_agent = MagicMock()
sys.modules["app.agents.factory"] = _factory

_chroma = types.ModuleType("chromadb")
sys.modules["chromadb"] = _chroma

_redis = types.ModuleType("redis")
_redis.__path__ = []
_redis.asyncio = types.ModuleType("redis.asyncio")
_redis.asyncio.Redis = MagicMock()
sys.modules["redis"] = _redis
sys.modules["redis.asyncio"] = _redis.asyncio

_otel = types.ModuleType("opentelemetry")
_otel.__path__ = []
_otel_trace = types.ModuleType("opentelemetry.trace")
_otel_trace.get_tracer = MagicMock(return_value=MagicMock())
sys.modules["opentelemetry"] = _otel
sys.modules["opentelemetry.trace"] = _otel_trace
_otel_sdk = types.ModuleType("opentelemetry.sdk")
_otel_sdk.__path__ = []
_res = types.ModuleType("opentelemetry.sdk.resources")
_res.Resource = MagicMock()
_tr = types.ModuleType("opentelemetry.sdk.trace")
_tr.TracerProvider = MagicMock()
_exp = types.ModuleType("opentelemetry.sdk.trace.export")
_exp.BatchSpanProcessor = MagicMock()
_exp.ConsoleSpanExporter = MagicMock()
sys.modules["opentelemetry.sdk"] = _otel_sdk
sys.modules["opentelemetry.sdk.resources"] = _res
sys.modules["opentelemetry.sdk.trace"] = _tr
sys.modules["opentelemetry.sdk.trace.export"] = _exp

from app.api.routes.chat import export_session  # noqa: E402
from app.db.crud import add_chat_message, create_chat_session  # noqa: E402
from app.models.schemas import Principal  # noqa: E402


async def _seed_session(db) -> str:
    """Create an acme-tenant session with a short two-turn transcript."""
    session = await create_chat_session(db, tenant_id="acme", department="sales")
    sid = str(session.id)
    await add_chat_message(
        db, session_id=sid, role="user",
        content="Summarize our sales pipeline and draft a follow-up email 🚀",
        department="reception",
    )
    await add_chat_message(
        db, session_id=sid, role="agent",
        content="Transferring you to the Sales department…",
        department="reception", agent_name="Riley",
    )
    await add_chat_message(
        db, session_id=sid, role="agent",
        content="Pipeline stands at 240,000 across 6 open deals.",
        department="sales", agent_name="Marcus",
    )
    await db.commit()
    return sid


async def _read_stream(resp) -> bytes:
    chunks = []
    async for chunk in resp.body_iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else str(chunk).encode())
    return b"".join(chunks)


@pytest.mark.asyncio
async def test_txt_export_is_readable_transcript(db_session):
    sid = await _seed_session(db_session)
    resp = await export_session(
        session_id=sid, format="txt",
        principal=Principal(user_id="acmeadmin", tenant_id="acme"),
        db=db_session,
    )
    body = (await _read_stream(resp)).decode("utf-8")

    assert resp.media_type.startswith("text/plain")
    assert "Summarize our sales pipeline" in body
    assert "Riley:" in body and "Marcus:" in body
    assert "You:" in body                      # friendly speaker label
    assert "[" in body and "]" in body         # [timestamp] labels


@pytest.mark.asyncio
async def test_pdf_export_is_real_pdf(db_session):
    import re
    import zlib

    sid = await _seed_session(db_session)
    resp = await export_session(
        session_id=sid, format="pdf",
        principal=Principal(user_id="acmeadmin", tenant_id="acme"),
        db=db_session,
    )
    body = await _read_stream(resp)

    assert resp.media_type == "application/pdf"
    assert body.startswith(b"%PDF")            # real PDF magic
    # Header band text lives inside compressed content streams — decompress.
    streams = re.findall(rb"stream\r?\n(.*?)endstream", body, re.DOTALL)
    raw = b""
    for s in streams:
        s = s.strip(b"\r\n")
        if not s:
            continue
        try:
            raw += zlib.decompress(s)
        except zlib.error:
            raw += s
    assert b"Conversation Transcript" in raw


@pytest.mark.asyncio
async def test_pdf_export_survives_non_latin1_content(db_session):
    """Emoji/unicode in messages must not crash the latin-1 PDF renderer."""
    sid = await _seed_session(db_session)
    resp = await export_session(
        session_id=sid, format="pdf",
        principal=Principal(user_id="acmeadmin", tenant_id="acme"),
        db=db_session,
    )
    assert (await _read_stream(resp)).startswith(b"%PDF")


@pytest.mark.asyncio
async def test_export_is_tenant_scoped(db_session):
    from fastapi import HTTPException

    sid = await _seed_session(db_session)
    for fmt in ("txt", "pdf"):
        with pytest.raises(HTTPException) as excinfo:
            await export_session(
                session_id=sid, format=fmt,
                principal=Principal(user_id="intruder", tenant_id="globex"),
                db=db_session,
            )
        assert excinfo.value.status_code == 404
