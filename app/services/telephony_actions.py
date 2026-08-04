"""Outbound telephony actions via the Vapi REST API.

Wraps Vapi's ``POST /call`` endpoint so department agents (Sales, Marketing,
Customer Care) and the admin UI can trigger a REAL outbound phone call to a
lead/customer using the same assistant that answers inbound calls.

Docs: https://docs.vapi.ai/api-reference/calls/create
"""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import logger

_VAPI_BASE_URL = "https://api.vapi.ai"


async def place_outbound_call(
    *,
    phone_number: str,
    reason: str = "",
    assistant_id: str | None = None,
) -> dict[str, Any]:
    """Place an outbound call via Vapi.

    Never raises — callers (agents, API endpoints) get a structured
    ``{"success": bool, "summary": str, ...}`` result even on failure so the
    conversation/UI can degrade gracefully instead of crashing.
    """
    api_key = settings.vapi_api_key
    aid = assistant_id or settings.vapi_assistant_id
    phone_number = (phone_number or "").strip()

    if not api_key or not aid:
        return {
            "success": False,
            "summary": "Outbound calling is not configured (missing Vapi API key or assistant ID).",
        }
    if not phone_number.startswith("+"):
        return {
            "success": False,
            "summary": f"Invalid phone number '{phone_number}' — must be in E.164 format, e.g. +6591234567.",
        }

    payload: dict[str, Any] = {
        "assistantId": aid,
        "customer": {"number": phone_number},
    }
    if reason:
        payload["assistantOverrides"] = {"variableValues": {"call_reason": reason}}
    if settings.vapi_phone_number_id:
        payload["phoneNumberId"] = settings.vapi_phone_number_id

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_VAPI_BASE_URL}/call",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        if resp.status_code >= 400:
            logger.warning("Vapi outbound call failed ({}): {}", resp.status_code, resp.text)
            return {"success": False, "summary": f"Vapi rejected the call request: {resp.text[:300]}"}
        data = resp.json()
        return {
            "success": True,
            "summary": f"Outbound call placed to {phone_number} (Vapi call id: {data.get('id', 'n/a')}).",
            "call_id": data.get("id"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vapi outbound call exception: {}", exc)
        return {"success": False, "summary": f"Could not reach Vapi: {exc}"}
