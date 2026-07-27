"""Shared company-branding / call-script helpers for voice telephony paths.

Extracted from ``app.voice.audiosocket_server`` so that both the legacy
Asterisk/AudioSocket path and the new Vapi webhook path can resolve the same
admin-configured greeting / transfer / department-intro scripts (Settings ->
Call Scripts) without duplicating logic.
"""
from __future__ import annotations

from app.core.config import settings

GREETING = "Thank you for calling AI Algo, how can I assist you?"
HOLD_PHRASE = "One moment, connecting you now."

DEPT_LABELS = {
    "reception": "Reception", "customer_care": "Customer Care",
    "sales": "Sales", "hr": "Human Resources", "finance": "Finance",
    "technology": "Technology", "marketing": "Marketing",
}

DEPT_INTROS = {
    "reception":      "Hi, this is Reception. How can I help you?",
    "customer_care":  "Hi there! I'm from Customer Care. I'm here to resolve your issue.",
    "sales":          "Hi! I'm your Sales agent. I can help with pricing, products, and purchases.",
    "hr":             "Hello! I'm the HR agent. I can assist with employment and HR queries.",
    "finance":        "Hi, this is Finance. I can help with billing, invoices, and payments.",
    "technology":     "Hello! This is Tech Support. I'm here to help with your technical issue.",
    "marketing":      "Hi! I'm the Marketing agent. I can help with campaigns and branding.",
}


async def get_branding(tenant_id: str = "default"):
    """Fetch (cached) company branding so voice scripts reflect Settings UI edits."""
    from app.core.company import get_company_branding

    try:
        return await get_company_branding(tenant_id)
    except Exception:  # noqa: BLE001
        return None


def dept_override(branding, department: str) -> dict:
    if branding is None:
        return {}
    return (branding.agent_overrides or {}).get(department) or {}


def company_greeting(branding, department: str = "reception") -> str:
    """Resolve the opening greeting for `department`, preferring the admin's
    configured script (Settings -> Call Scripts) over the hardcoded default."""
    override = dept_override(branding, department)
    custom = (override.get("greeting") or override.get("script") or "").strip()
    if custom:
        company_name = (branding.company_name if branding else None) or settings.company_name
        try:
            return custom.format(company_name=company_name, department=department)
        except (KeyError, IndexError):
            return custom
    return GREETING


def company_transfer_message(branding, department: str) -> str:
    """Resolve the phrase spoken while transferring OUT of `department`."""
    override = dept_override(branding, department)
    custom = (override.get("transfer_message") or "").strip()
    return custom or HOLD_PHRASE


def company_dept_intro(branding, department: str) -> str:
    """Resolve the greeting spoken by the NEW department right after a transfer."""
    override = dept_override(branding, department)
    custom = (override.get("greeting") or override.get("script") or "").strip()
    if custom:
        company_name = (branding.company_name if branding else None) or settings.company_name
        try:
            return custom.format(company_name=company_name, department=department)
        except (KeyError, IndexError):
            return custom
    return DEPT_INTROS.get(
        department,
        f"Hi, this is {DEPT_LABELS.get(department, department.replace('_', ' ').title())}. How can I help you?",
    )
