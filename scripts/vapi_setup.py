"""One-off / re-runnable script to create or update the Vapi Assistant so it
reflects our current company greeting, call scripts, and product catalog.

Run this after any admin edit to Settings -> Call Scripts or the Products
catalog (or wire it to auto-run from the settings-save handler) so Vapi's
assistant always speaks with up-to-date, non-hallucinated content.

Usage (from the backend container / venv):
    python -m scripts.vapi_setup

Requires env vars:
    VAPI_API_KEY        - private API key from the Vapi dashboard
    VAPI_ASSISTANT_ID   - (optional) existing assistant to update; if unset,
                           a new assistant is created and its id is printed
                           so you can save it back into VAPI_ASSISTANT_ID.
    BACKEND_PUBLIC_URL   - publicly reachable base URL of this backend,
                           e.g. https://api.yourdomain.com (used to build the
                           serverUrl Vapi calls for tool-calls/end-of-call).
"""
from __future__ import annotations

import asyncio
import os
import sys

import aiohttp

VAPI_BASE = "https://api.vapi.ai"


async def _fetch_company_context(tenant_id: str = "default") -> dict:
    """Pull greeting/company name/products from our own DB so the Vapi
    assistant prompt and first message match what's configured in the UI."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.core.company import get_company_branding
    from app.db.session import AsyncSessionLocal
    from app.db.models import ProductModel
    from sqlalchemy import select

    branding = await get_company_branding(tenant_id)
    company_name = (branding.company_name if branding else None) or "AI Algo"
    greeting_override = (
        (branding.agent_overrides or {}).get("reception", {}).get("greeting")
        if branding else None
    )
    greeting = (greeting_override or "").strip() or (
        f"Thank you for calling {company_name}, how can I assist you?"
    )

    products: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(ProductModel).where(ProductModel.tenant_id == tenant_id))).scalars().all()
            products = [f"{p.name}: {p.description or ''}".strip() for p in rows]
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: could not load products ({exc}); assistant will rely on live KB lookups only.")

    return {"company_name": company_name, "greeting": greeting, "products": products}


def _build_assistant_payload(server_url: str, context: dict) -> dict:
    product_list = "\n".join(f"- {p}" for p in context["products"][:50]) or "(use the search_knowledge_base tool to look up products live)"

    # NOTE: gpt-realtime-2 is a native speech-to-speech model — it replaces the
    # separate transcriber + LLM + TTS pipeline (no `transcriber` config, and the
    # voice must be one of OpenAI's realtime voices: alloy/echo/shimmer/marin/cedar).
    system_prompt = (
        f"# Role & Objective\n"
        f"You are the warm, professional phone receptionist for {context['company_name']}. "
        "Greet callers warmly, help them with our products and services, and connect them to the right department when needed.\n\n"
        "# Personality & Tone\n"
        "- Friendly, professional, and empathetic, like a real front-desk person\n"
        "- Speak naturally and conversationally, never robotic\n"
        "- Keep responses short (2-3 sentences) unless the caller asks for detail\n\n"
        "# Pacing\n"
        "- Speak at a natural, unhurried conversational speed\n"
        "- Pause briefly between key points\n"
        "- If the caller interrupts you or asks a question mid-explanation, STOP, answer their question first, then resume only if still relevant\n"
        "- Wait for the caller to finish speaking before responding\n\n"
        "# Grounding (STRICT)\n"
        "- ONLY discuss products/services that are in the list below or returned by the search_knowledge_base tool\n"
        "- NEVER invent, assume, or improvise details, prices, or services not explicitly provided\n"
        "- If unsure, say you will check and follow up\n\n"
        f"# Our current products/services\n{product_list}\n\n"
        "# Transfers\n"
        "- When the caller needs a different department, call the transfer_department tool with one of: "
        "reception, customer_care, sales, hr, finance, technology, marketing\n"
        "- BEFORE calling it, tell the caller you are connecting them now so there is no dead silence\n\n"
        "# Taking details\n"
        "- When taking down a name, ask the caller to spell it\n"
        "- When taking a phone number, repeat it back digit by digit to confirm\n"
        "- When taking an email, spell it back letter by letter"
    )

    return {
        "name": f"{context['company_name']} Receptionist",
        "firstMessage": context["greeting"],
        "model": {
            "provider": "openai",
            "model": "gpt-realtime-2",
            "temperature": 0.6,
            "maxTokens": 300,
            "messages": [{"role": "system", "content": system_prompt}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_knowledge_base",
                        "description": "Look up grounded, factual info about our products, services, or policies before answering any question you're not 100% certain about.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The caller's question or topic to search for"},
                                "department": {"type": "string", "description": "Optional department context, e.g. sales, technology"},
                            },
                            "required": ["query"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "transfer_department",
                        "description": "Transfer the caller to a different department when they ask for one, or their need matches that department.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "department": {
                                    "type": "string",
                                    "enum": ["reception", "customer_care", "sales", "hr", "finance", "technology", "marketing"],
                                },
                            },
                            "required": ["department"],
                        },
                    },
                },
            ],
        },
        "voice": {"provider": "openai", "voiceId": "echo"},
        "transcriber": None,  # realtime models transcribe natively — no separate STT
        "serverUrl": server_url,
        "serverMessages": ["tool-calls", "end-of-call-report"],
        "endCallFunctionEnabled": True,
        "silenceTimeoutSeconds": 30,
        "backgroundSound": "off",
    }


async def main() -> None:
    api_key = os.getenv("VAPI_API_KEY", "")
    if not api_key:
        print("ERROR: VAPI_API_KEY env var is required.")
        sys.exit(1)

    backend_url = os.getenv("BACKEND_PUBLIC_URL", "").rstrip("/")
    if not backend_url:
        print("ERROR: BACKEND_PUBLIC_URL env var is required (e.g. https://api.yourdomain.com).")
        sys.exit(1)
    server_url = f"{backend_url}/api/v1/vapi/webhook"

    assistant_id = os.getenv("VAPI_ASSISTANT_ID", "")
    context = await _fetch_company_context()
    payload = _build_assistant_payload(server_url, context)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as sess:
        if assistant_id:
            url = f"{VAPI_BASE}/assistant/{assistant_id}"
            async with sess.patch(url, headers=headers, json=payload) as resp:
                body = await resp.json()
                if resp.status not in (200, 201):
                    print(f"Update failed ({resp.status}): {body}")
                    sys.exit(1)
                print(f"Updated Vapi assistant {assistant_id} OK.")
        else:
            url = f"{VAPI_BASE}/assistant"
            async with sess.post(url, headers=headers, json=payload) as resp:
                body = await resp.json()
                if resp.status not in (200, 201):
                    print(f"Create failed ({resp.status}): {body}")
                    sys.exit(1)
                new_id = body.get("id")
                print(f"Created Vapi assistant {new_id}.")
                print("Save this as VAPI_ASSISTANT_ID in your .env, then re-run this script for future syncs.")


if __name__ == "__main__":
    asyncio.run(main())
