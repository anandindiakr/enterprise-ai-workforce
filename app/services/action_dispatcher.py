"""Action dispatcher — lets department agents perform REAL actions.

Swarms' native OpenAI function-calling is intentionally disabled on our
``Agent`` instances (see ``app.agents.factory``) because Swarms 9.x returns
``None`` when the model answers in plain text while tools are registered.

This module reimplements the same *proven* pattern already used successfully
on the live phone-call path (``app.api.routes.vapi``) — a lightweight,
independent OpenAI function-calling decision pass — and generalises it to
every department across chat and voice:

1. Build the live tool schema for the requesting department from the MCP
   registry (CRM, HRIS, ERP, ticketing, calendar, email, analytics) plus a
   couple of built-in actions (outbound call, social post draft).
2. Ask a small, cheap model whether the user's message actually warrants
   calling one of those tools right now.
3. Execute any requested tool call for real (MCP registry call, or the
   dedicated outbound-call/social-draft handler).
4. Publish a live event on the ``orchestration`` broadcast channel (consumed
   by the admin "Live Orchestration" view) and write an audit-log row.
5. Return a short context string to inject into the main agent's task so it
   can mention the action naturally, plus the structured results for the
   API response.

Never raises: any failure here silently degrades to "no action taken" so a
broken/unconfigured connector never breaks the conversation.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from app.core.broadcast import bus
from app.core.logging import logger
from app.core.types import Department
from app.mcp import mcp_registry

# Departments allowed to trigger a REAL outbound phone call via Vapi.
_OUTBOUND_CALL_DEPARTMENTS = {Department.SALES, Department.MARKETING, Department.CUSTOMER_CARE}
# Departments allowed to draft a social post (text only — no auto-publish).
_SOCIAL_DRAFT_DEPARTMENTS = {Department.MARKETING}


@dataclass(slots=True)
class ActionResult:
    connector: str
    tool: str
    success: bool
    summary: str
    data: Any = None


def _builtin_tools(department: Department) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    if department in _OUTBOUND_CALL_DEPARTMENTS:
        tools.append({
            "type": "function",
            "function": {
                "name": "__place_outbound_call",
                "description": (
                    "Place a REAL outbound phone call to a customer/lead via the "
                    "Vapi telephony platform. Use ONLY when the user explicitly "
                    "asks to be called back, or asks the agent to call a specific "
                    "phone number right now."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone_number": {
                            "type": "string",
                            "description": "E.164 phone number to call, e.g. +6591234567",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Short reason for the call, given to the assistant as context",
                        },
                    },
                    "required": ["phone_number"],
                },
            },
        })
    if department in _SOCIAL_DRAFT_DEPARTMENTS:
        tools.append({
            "type": "function",
            "function": {
                "name": "__draft_social_post",
                "description": (
                    "Draft a ready-to-copy social media post about a product, "
                    "offer, or announcement. Does NOT publish anything "
                    "automatically — returns text for a human to review and post."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "platform": {
                            "type": "string",
                            "enum": ["linkedin", "twitter", "facebook", "instagram"],
                        },
                        "topic": {"type": "string", "description": "What the post should be about"},
                    },
                    "required": ["platform", "topic"],
                },
            },
        })
    return tools


def _mcp_tools_schema(department: Department) -> list[dict[str, Any]]:
    """Build OpenAI function-calling schema from live MCP tool metadata."""
    out: list[dict[str, Any]] = []
    for connector_name, tool in mcp_registry().list_tools(department):
        schema = tool.input_schema or {"type": "object", "properties": {}}
        out.append({
            "type": "function",
            "function": {
                "name": f"mcp__{connector_name}__{tool.name}",
                "description": tool.description or f"{connector_name} tool: {tool.name}",
                "parameters": schema,
            },
        })
    return out


async def _run_outbound_call(arguments: dict[str, Any]) -> ActionResult:
    from app.services.telephony_actions import place_outbound_call

    result = await place_outbound_call(
        phone_number=arguments.get("phone_number", ""),
        reason=arguments.get("reason", ""),
    )
    return ActionResult(
        connector="vapi",
        tool="place_outbound_call",
        success=bool(result.get("success")),
        summary=result.get("summary", "Outbound call requested."),
        data=result,
    )


async def _run_social_draft(arguments: dict[str, Any]) -> ActionResult:
    platform = arguments.get("platform", "linkedin")
    topic = arguments.get("topic", "")
    summary = f"Drafted a {platform.title()} post about: {topic}"
    return ActionResult(
        connector="social",
        tool="draft_social_post",
        success=True,
        summary=summary,
        data={"platform": platform, "topic": topic},
    )


async def _execute_tool_call(name: str, arguments: dict[str, Any]) -> ActionResult:
    if name == "__place_outbound_call":
        return await _run_outbound_call(arguments)
    if name == "__draft_social_post":
        return await _run_social_draft(arguments)
    if name.startswith("mcp__"):
        try:
            _, connector_name, tool_name = name.split("__", 2)
        except ValueError:
            return ActionResult(connector="unknown", tool=name, success=False, summary=f"Malformed action name: {name}")
        result = await mcp_registry().call(connector_name, tool_name, arguments)
        summary = (
            f"{tool_name} on {connector_name} succeeded"
            if result.success
            else f"{tool_name} on {connector_name} failed: {result.error}"
        )
        return ActionResult(
            connector=connector_name, tool=tool_name, success=result.success, summary=summary, data=result.data,
        )
    return ActionResult(connector="unknown", tool=name, success=False, summary=f"Unknown action: {name}")


async def _audit(*, tenant_id: str | None, user_id: str | None, session_id: str,
                  department: Department, result: ActionResult) -> None:
    try:
        from app.db.crud import write_audit_log
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            await write_audit_log(
                db,
                tenant_id=tenant_id or "default",
                user_id=user_id,
                action=f"agent_action.{result.connector}.{result.tool}",
                resource_type="agent_action",
                resource_id=session_id,
                details={
                    "success": result.success,
                    "summary": result.summary[:500],
                    "department": department.value,
                },
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Audit log write skipped: {}", exc)


async def dispatch(
    *,
    department: Department,
    message: str,
    session_id: str,
    tenant_id: str | None,
    user_id: str | None = None,
    history: list[Any] | None = None,
) -> tuple[str, list[ActionResult]]:
    """Decide + execute any real tool actions warranted by this user turn.

    ``history`` is the recent conversation (most-recent-last), used so a
    multi-turn action (e.g. "log a ticket" -> agent asks for contact info ->
    user replies "Anand, +65...") is still recognised on the follow-up turn
    instead of looking at the latest message in isolation.

    Returns ``(context_to_inject, action_results)``. Never raises — on any
    failure it returns ``("", [])`` so the chat flow is unaffected.
    """
    import os

    from app.core.config import settings

    openai_key = getattr(settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        logger.info("Action dispatch skipped: no OPENAI_API_KEY configured")
        return "", []

    tools = _mcp_tools_schema(department) + _builtin_tools(department)
    if not tools:
        logger.info("Action dispatch skipped: no tools available for department={}", department.value)
        return "", []

    history_messages: list[dict[str, str]] = []
    for msg in (history or [])[-6:]:
        role = "assistant" if str(getattr(msg, "role", "")).lower() in ("agent", "assistant") else "user"
        content = str(getattr(msg, "content", "") or "")
        if content:
            history_messages.append({"role": role, "content": content[:1000]})

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=openai_key)
        completion = await client.chat.completions.create(
            model=getattr(settings, "openai_model", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You decide whether the CURRENT user message — read in "
                        "the context of the recent conversation below — requires "
                        "calling a backend tool/action right now (e.g. creating a "
                        "CRM lead, opening a support ticket, checking an invoice, "
                        "booking a meeting, placing an outbound call, drafting a "
                        "social post). This includes follow-up replies that supply "
                        "information an earlier agent message asked for (e.g. a "
                        "name/phone/email given right after the agent said it would "
                        "log a ticket) — treat that as completing the action. Only "
                        "call a tool when a real action is clearly warranted — not "
                        "for a general question, opinion, or small talk. If no "
                        "action is needed, do not call any tool."
                    ),
                },
                *history_messages,
                {"role": "user", "content": message},
            ],
            tools=tools,
            tool_choice="auto",
            max_tokens=300,
            temperature=0,
        )
        tool_calls = completion.choices[0].message.tool_calls or []
        logger.info(
            "Action dispatch decision: department={} tools_available={} tool_calls_chosen={}",
            department.value, len(tools), [c.function.name for c in tool_calls],
        )
        if not tool_calls:
            return "", []

        results: list[ActionResult] = []
        for call in tool_calls[:3]:  # safety cap per turn
            try:
                args = json.loads(call.function.arguments or "{}")
            except Exception:  # noqa: BLE001
                args = {}

            result = await _execute_tool_call(call.function.name, args)
            results.append(result)

            await bus.publish("orchestration", {
                "type": "tool_call",
                "department": department.value,
                "connector": result.connector,
                "tool": result.tool,
                "success": result.success,
                "summary": result.summary[:300],
                "session_id": session_id,
                "tenant_id": tenant_id,
                "ts": time.time(),
            })
            await _audit(tenant_id=tenant_id, user_id=user_id, session_id=session_id,
                         department=department, result=result)

        context_lines = "\n".join(f"- {r.tool} ({r.connector}): {r.summary}" for r in results)
        context = f"[Actions just taken on your behalf]\n{context_lines}"
        return context, results
    except Exception as exc:  # noqa: BLE001
        logger.exception("Action dispatch failed for department={}: {}", department.value, exc)
        return "", []
