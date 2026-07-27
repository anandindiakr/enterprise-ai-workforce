"""Vapi voice-platform webhook integration.

Vapi (https://vapi.ai) owns the phone call itself — SIP trunking, STT, TTS,
and natural turn-taking/barge-in. Our FastAPI backend stays the "brain": it
answers Vapi's tool-call webhooks with knowledge-base-grounded answers,
resolves department transfers using the same admin-configured scripts as the
legacy Asterisk path (see `app.voice.branding`), and generates a call summary
+ notification email once the call ends.

Vapi server-message reference: https://docs.vapi.ai/server-url
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger
from app.services.chat_service import _retrieve_kb_context
from app.services.notification_service import send_generic_email
from app.voice import branding

router = APIRouter(prefix="/vapi", tags=["vapi"])


def _verify_secret(received: str | None) -> bool:
    """Verify the shared webhook secret Vapi sends on every server message.

    Vapi supports either a plain shared-secret header or an HMAC signature,
    depending on how the phone number / assistant is configured. We accept
    either: a direct match, or a valid `sha256=` HMAC of no body (best-effort;
    Vapi's dashboard "server URL secret" field is the plain-match mode we
    document in `.env.example`). If no secret is configured we skip
    verification entirely (useful for local testing before Vapi is wired).
    """
    secret = settings.vapi_webhook_secret
    if not secret:
        return True
    if not received:
        return False
    return hmac.compare_digest(received, secret)


@router.post("/webhook")
async def vapi_webhook(
    request: Request,
    x_vapi_secret: str | None = Header(default=None, alias="x-vapi-secret"),
    x_vapi_signature: str | None = Header(default=None, alias="x-vapi-signature"),
) -> JSONResponse:
    """Single server-URL endpoint Vapi calls for tool-calls, transcripts, and
    the end-of-call report. Configure this URL (https://<your-domain>/api/v1/vapi/webhook)
    as the Assistant's `serverUrl` in the Vapi dashboard / `scripts/vapi_setup.py`.
    """
    if not _verify_secret(x_vapi_secret or x_vapi_signature):
        logger.warning("Vapi webhook: signature/secret verification failed")
        return JSONResponse(status_code=401, content={"error": "invalid signature"})

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    message = payload.get("message") or {}
    msg_type = message.get("type")
    tenant_id = os.getenv("VAPI_DEFAULT_TENANT", "default")

    try:
        if msg_type in ("tool-calls", "function-call"):
            return JSONResponse(content=await _handle_tool_calls(message, tenant_id))
        if msg_type == "end-of-call-report":
            await _handle_end_of_call(message, tenant_id)
            return JSONResponse(content={"received": True})
        # assistant-request, status-update, transcript, hang, speech-update, etc.
        # No action needed — acknowledge so Vapi doesn't retry.
        return JSONResponse(content={"received": True})
    except Exception as exc:  # noqa: BLE001
        logger.error("Vapi webhook handler error ({}): {}", msg_type, exc)
        # Still return 200 so Vapi doesn't hang up the call on our error.
        return JSONResponse(content={"received": True, "error": str(exc)})


async def _handle_tool_calls(message: dict[str, Any], tenant_id: str) -> dict[str, Any]:
    """Handle Vapi's `tool-calls` / legacy `function-call` server messages.

    Newer Vapi payloads carry `message.toolCallList` (each with `id`, `name`,
    `arguments`); the legacy shape carries a single `message.functionCall`.
    We respond with `results` keyed by tool-call id, per Vapi's contract.
    """
    tool_calls = message.get("toolCallList") or message.get("toolCalls") or []
    if not tool_calls and message.get("functionCall"):
        fc = message["functionCall"]
        tool_calls = [{"id": fc.get("name", "call_1"), "name": fc.get("name"), "arguments": fc.get("parameters") or {}}]

    results = []
    for call in tool_calls:
        call_id = call.get("id") or call.get("toolCallId") or call.get("name")
        name = call.get("name") or (call.get("function") or {}).get("name")
        args = call.get("arguments") or (call.get("function") or {}).get("arguments") or {}
        if isinstance(args, str):
            import json as _json
            try:
                args = _json.loads(args)
            except Exception:  # noqa: BLE001
                args = {}

        if name == "search_knowledge_base":
            result_text = await _tool_search_knowledge_base(args, tenant_id)
        elif name == "transfer_department":
            result_text = await _tool_transfer_department(args, tenant_id)
        else:
            result_text = f"Unknown tool: {name}"

        results.append({"toolCallId": call_id, "result": result_text})

    return {"results": results}


async def _tool_search_knowledge_base(args: dict[str, Any], tenant_id: str) -> str:
    query = str(args.get("query") or "").strip()
    department = args.get("department")
    if not query:
        return "No search query provided."
    kb = await _retrieve_kb_context(query, tenant_id, department=department)
    if not kb:
        return (
            "No matching documents found in the knowledge base for this query. "
            "Do not invent products, services, or details — tell the caller you don't "
            "have that information and offer to have someone follow up."
        )
    return kb


async def _tool_transfer_department(args: dict[str, Any], tenant_id: str) -> str:
    department = str(args.get("department") or "").strip().lower()
    if not department:
        return "No department specified for transfer."

    company = await branding.get_branding(tenant_id)
    transfer_msg = branding.company_transfer_message(company, department)
    dept_intro = branding.company_dept_intro(company, department)
    label = branding.DEPT_LABELS.get(department, department.replace("_", " ").title())

    return (
        f"TRANSFER_ACK: {transfer_msg} "
        f"You are now speaking as the {label} department. Greet the caller with: "
        f"\"{dept_intro}\" then continue the conversation naturally in that role."
    )


async def _handle_end_of_call(message: dict[str, Any], tenant_id: str) -> None:
    """Generate a call summary (tone / outcome / next steps) and, if the call
    looks like a lead or open issue, email the admin (and the caller, if we
    captured their email) — mirrors the existing chat-service escalation flow.
    """
    call = message.get("call") or {}
    transcript = message.get("transcript") or message.get("artifact", {}).get("transcript") or ""
    summary_field = message.get("summary") or ""
    ended_reason = message.get("endedReason") or call.get("endedReason") or "unknown"
    customer_number = (call.get("customer") or {}).get("number") or "unknown"

    if not transcript and not summary_field:
        logger.info("Vapi end-of-call-report: no transcript/summary available, skipping email")
        return

    summary_text = await _generate_call_summary(transcript, summary_field)

    to_addr = settings.escalation_email_to or os.getenv("ESCALATION_EMAIL_TO", "")
    if not to_addr:
        logger.info("Vapi end-of-call-report: no admin email configured, summary only logged")
        logger.info("Call summary ({}): {}", customer_number, summary_text)
        return

    subject = f"Call summary — {customer_number} ({ended_reason})"
    body = (
        f"A phone call just ended.\n\n"
        f"Caller: {customer_number}\n"
        f"Ended reason: {ended_reason}\n\n"
        f"--- Summary ---\n{summary_text}\n\n"
        f"--- Raw transcript ---\n{transcript[:4000] if isinstance(transcript, str) else transcript}\n"
    )
    result = await send_generic_email(to_addr, subject, body)
    logger.info("Vapi call-summary email result: {}", result)


async def _generate_call_summary(transcript: Any, fallback_summary: str) -> str:
    """Use OpenAI to produce a short tone/outcome/next-steps summary.

    Falls back to Vapi's own `summary` field (or a generic note) if no OpenAI
    key is configured or the call fails.
    """
    openai_key = getattr(settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY", "")
    transcript_text = transcript if isinstance(transcript, str) else str(transcript)

    if not openai_key or not transcript_text.strip():
        return fallback_summary or "No summary available."

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=openai_key)
        completion = await client.chat.completions.create(
            model=getattr(settings, "openai_model", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize this phone call transcript in 3 short sections: "
                        "Tone (caller's mood/attitude), Outcome (what was resolved or discussed), "
                        "and Next Steps / Lead Potential (any follow-up needed, and whether this "
                        "caller shows buying/service interest). Be concise, factual, no invented details."
                    ),
                },
                {"role": "user", "content": transcript_text[:6000]},
            ],
            temperature=0.3,
            max_tokens=350,
        )
        return (completion.choices[0].message.content or fallback_summary or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Call summary generation failed: {}", exc)
        return fallback_summary or "Summary generation failed."
