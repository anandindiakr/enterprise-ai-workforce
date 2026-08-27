"""Unit tests for deterministic topic-based department transfer.

Verifies that a cross-department request sent to a pinned department
(Reception) is handed off deterministically when the agent reply signals
it couldn't help, instead of leaving the user with a generic refusal.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# The `swarms` package and agent factory are heavy Docker-image-only deps.
# Stub them out at module-load time so `app.services.chat_service` imports.
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

# ChromaDB / Redis / OpenTelemetry are optional runtime deps not present in
# the CI image. Stub them as importable (sub)modules.
_chroma = types.ModuleType("chromadb")
sys.modules["chromadb"] = _chroma

_redis = types.ModuleType("redis")
_redis.__path__ = []  # make it importable as a package
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

from app.core.types import Department, SwarmStrategy  # noqa: E402
from app.models.schemas import ChatRequest, WorkflowResult  # noqa: E402


def _fake_result(output: str) -> WorkflowResult:
    return WorkflowResult(
        department=Department.RECEPTION,
        strategy=SwarmStrategy.SEQUENTIAL,
        output=output,
        duration_ms=5,
        agents_involved=["Fake"],
        succeeded=True,
    )


class _FakeMemory:
    async def recent_history(self, session_id: str, limit: int) -> list:
        return []

    async def record_message(self, ctx, msg) -> None:
        return None


class _FakeRouter:
    def __init__(self, topic_dept: Department) -> None:
        self._topic = topic_dept

    def choose_department(self, task: str) -> Department:
        return self._topic

    async def execute(self, request) -> WorkflowResult:
        return _fake_result("I don't have direct access to your sales pipeline data.")


@pytest.mark.asyncio
@patch("app.services.chat_service._retrieve_kb_context", new=AsyncMock(return_value=""))
@patch("app.services.action_dispatcher.dispatch", new=AsyncMock(return_value=(None, [])))
async def test_reception_hands_off_sales_topic_deterministically():
    from app.services.chat_service import ChatService

    router = _FakeRouter(topic_dept=Department.SALES)
    with patch("app.services.chat_service.memory_manager", return_value=_FakeMemory()), \
         patch("app.services.chat_service.workforce_router", return_value=router), \
         patch("app.voice.session.workforce_router", return_value=router):
        resp = await ChatService().handle(
            ChatRequest(message="Summarize our sales pipeline and draft a follow-up email",
                        department=Department.RECEPTION)
        )

    assert resp.transferred_to == Department.SALES
    assert resp.department == Department.SALES
    assert "Sales" in (resp.message.content or "")


@pytest.mark.asyncio
@patch("app.services.chat_service._retrieve_kb_context", new=AsyncMock(return_value=""))
@patch("app.services.action_dispatcher.dispatch", new=AsyncMock(return_value=(None, [])))
async def test_no_transfer_when_topic_matches_pinned_department():
    from app.services.chat_service import ChatService

    router = _FakeRouter(topic_dept=Department.SALES)
    with patch("app.services.chat_service.memory_manager", return_value=_FakeMemory()), \
         patch("app.services.chat_service.workforce_router", return_value=router), \
         patch("app.voice.session.workforce_router", return_value=router):
        resp = await ChatService().handle(
            ChatRequest(message="Follow up on the BrainguardX deal", department=Department.SALES)
        )

    assert resp.transferred_to is None
    assert resp.department == Department.SALES


@pytest.mark.asyncio
@patch("app.services.chat_service._retrieve_kb_context", new=AsyncMock(return_value=""))
@patch("app.services.action_dispatcher.dispatch", new=AsyncMock(return_value=(None, [])))
async def test_substantive_answer_never_overwritten():
    """Guard: a real answer from the pinned agent must NOT be replaced by a
    deterministic transfer, even when the topic hints at another department."""
    from app.services.chat_service import ChatService

    class _AnsweringRouter(_FakeRouter):
        async def execute(self, request) -> WorkflowResult:
            return _fake_result(
                "Our enterprise plan starts at 10,000 per year and includes "
                "the full AI workforce across all seven departments."
            )

    router = _AnsweringRouter(topic_dept=Department.SALES)
    with patch("app.services.chat_service.memory_manager", return_value=_FakeMemory()), \
         patch("app.services.chat_service.workforce_router", return_value=router), \
         patch("app.voice.session.workforce_router", return_value=router):
        resp = await ChatService().handle(
            ChatRequest(message="What does your enterprise plan cost?", department=Department.RECEPTION)
        )

    assert resp.transferred_to is None
    assert resp.department == Department.RECEPTION
    assert "enterprise plan" in (resp.message.content or "").lower()


@pytest.mark.asyncio
@patch("app.services.chat_service._retrieve_kb_context", new=AsyncMock(return_value=""))
@patch("app.services.action_dispatcher.dispatch", new=AsyncMock(return_value=(None, [])))
async def test_handoff_answers_original_question():
    """After a transfer, the receiving department must answer the user's
    original question immediately — the reply must contain the handoff line
    AND the real answer, and the second swarm call must target the new dept."""
    from app.services.chat_service import ChatService

    calls: list[Department] = []

    class _HandoffRouter(_FakeRouter):
        async def execute(self, request) -> WorkflowResult:
            calls.append(request.department)
            if request.department == Department.SALES:
                return _fake_result(
                    "Pipeline stands at 240,000 across 6 open deals; the top "
                    "opportunity is BrainguardX at 80,000 — follow-up email drafted."
                )
            return _fake_result("I don't have direct access to your sales pipeline data.")

    router = _HandoffRouter(topic_dept=Department.SALES)
    with patch("app.services.chat_service.memory_manager", return_value=_FakeMemory()), \
         patch("app.services.chat_service.workforce_router", return_value=router), \
         patch("app.voice.session.workforce_router", return_value=router):
        resp = await ChatService().handle(
            ChatRequest(message="Summarize our sales pipeline and draft a follow-up email",
                        department=Department.RECEPTION)
        )

    assert resp.transferred_to == Department.SALES
    assert calls == [Department.RECEPTION, Department.SALES]
    content = resp.message.content or ""
    assert "Sales" in content          # handoff line
    assert "BrainguardX" in content    # the actual answer from Sales


# ---------------------------------------------------------------------------
# Multi-tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_owned_session_rejects_cross_tenant(db_session):
    """A session owned by another tenant must be invisible (404), not readable."""
    from fastapi import HTTPException

    from app.api.routes.chat import _get_owned_session
    from app.db.crud import create_chat_session

    session = await create_chat_session(db_session, tenant_id="acme", department="sales")
    sid = str(session.id)

    # Owner tenant can fetch it.
    owned = await _get_owned_session(db_session, sid, "acme")
    assert owned is not None

    # Another tenant sees 404 — no existence leak.
    with pytest.raises(HTTPException) as excinfo:
        await _get_owned_session(db_session, sid, "otherco")
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_owned_session_missing_is_404(db_session):
    from fastapi import HTTPException

    from app.api.routes.chat import _get_owned_session

    with pytest.raises(HTTPException) as excinfo:
        await _get_owned_session(db_session, "00000000-0000-0000-0000-000000000000", "acme")
    assert excinfo.value.status_code == 404
