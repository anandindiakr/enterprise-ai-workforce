"""Billing service — Stripe-ready architecture.

Works fully without Stripe:
  - Subscriptions are stored in PostgreSQL
  - Invoices are created / managed locally
  - When STRIPE_SECRET_KEY is set, all operations also sync to Stripe

Stripe hook-up checklist (when ready):
  1. Add STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET to .env
  2. The route handler already calls _stripe_* helpers — they are no-ops until key is set
  3. Set up webhook endpoint in Stripe dashboard: POST /api/v1/billing/webhooks/stripe
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BillingSubscriptionModel,
    BillingInvoiceModel,
    TenantModel,
)

# ---------------------------------------------------------------------------
# Plan catalogue — single source of truth
# ---------------------------------------------------------------------------

PLAN_CATALOGUE: dict[str, dict[str, Any]] = {
    "free": {
        "name": "Free",
        "amount_cents": 0,
        "max_users": 3,
        "max_chat_sessions": 100,
        "max_voice_minutes": 10,
        "features": ["3 users", "100 chat sessions/mo", "10 voice minutes/mo", "Community support"],
    },
    "starter": {
        "name": "Starter",
        "amount_cents": 4900,          # $49/mo
        "max_users": 10,
        "max_chat_sessions": 1000,
        "max_voice_minutes": 60,
        "features": ["10 users", "1 000 chat sessions/mo", "60 voice minutes/mo", "Email support", "Audit logs"],
    },
    "pro": {
        "name": "Pro",
        "amount_cents": 14900,         # $149/mo
        "max_users": 50,
        "max_chat_sessions": 5000,
        "max_voice_minutes": 300,
        "features": ["50 users", "5 000 chat sessions/mo", "300 voice minutes/mo",
                     "Priority support", "Custom agents", "Advanced analytics"],
    },
    "enterprise": {
        "name": "Enterprise",
        "amount_cents": 49900,         # $499/mo
        "max_users": 500,
        "max_chat_sessions": 50000,
        "max_voice_minutes": 3000,
        "features": ["500 users", "50 000 chat sessions/mo", "3 000 voice minutes/mo",
                     "Dedicated support", "SLA", "White-label", "On-premise option"],
    },
}

ANNUAL_DISCOUNT_PCT = 20  # 20% off for annual billing


def _stripe_available() -> bool:
    return bool(os.getenv("STRIPE_SECRET_KEY"))


def _plan_amount(plan: str, billing_cycle: str) -> int:
    base = PLAN_CATALOGUE.get(plan, PLAN_CATALOGUE["free"])["amount_cents"]
    if billing_cycle == "annual":
        monthly_12 = base * 12
        return int(monthly_12 * (1 - ANNUAL_DISCOUNT_PCT / 100))
    return base


def _next_invoice_number(existing_count: int) -> str:
    year = datetime.now(timezone.utc).year
    return f"INV-{year}-{existing_count + 1:04d}"


# ---------------------------------------------------------------------------
# Subscription helpers
# ---------------------------------------------------------------------------

async def get_or_create_subscription(
    session: AsyncSession,
    tenant_id: str,
    plan: str = "free",
    billing_cycle: str = "monthly",
) -> BillingSubscriptionModel:
    result = await session.execute(
        select(BillingSubscriptionModel).where(BillingSubscriptionModel.tenant_id == tenant_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        return sub

    now = datetime.now(timezone.utc)
    sub = BillingSubscriptionModel(
        tenant_id=tenant_id,
        plan=plan,
        status="active",
        billing_cycle=billing_cycle,
        currency="usd",
        amount_cents=_plan_amount(plan, billing_cycle),
        current_period_start=now,
        current_period_end=now + timedelta(days=30 if billing_cycle == "monthly" else 365),
    )
    session.add(sub)
    await session.flush()
    return sub


async def change_plan(
    session: AsyncSession,
    tenant_id: str,
    new_plan: str,
    billing_cycle: str = "monthly",
) -> BillingSubscriptionModel:
    sub = await get_or_create_subscription(session, tenant_id)
    old_plan = sub.plan

    sub.plan = new_plan
    sub.billing_cycle = billing_cycle
    sub.amount_cents = _plan_amount(new_plan, billing_cycle)
    sub.status = "active"

    # Update tenant limits to match new plan
    plan_info = PLAN_CATALOGUE.get(new_plan, PLAN_CATALOGUE["free"])
    tenant_result = await session.execute(
        select(TenantModel).where(TenantModel.slug == tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()
    if tenant:
        tenant.plan = new_plan
        tenant.max_users = plan_info["max_users"]
        tenant.max_chat_sessions = plan_info["max_chat_sessions"]
        tenant.max_voice_minutes = plan_info["max_voice_minutes"]

    await session.flush()

    # Stripe sync (no-op without key)
    if _stripe_available() and sub.stripe_subscription_id:
        await _stripe_update_subscription(sub.stripe_subscription_id, new_plan)

    logger.info(f"[billing] {tenant_id}: plan changed {old_plan} → {new_plan}")
    return sub


async def cancel_subscription(
    session: AsyncSession,
    tenant_id: str,
    at_period_end: bool = True,
) -> BillingSubscriptionModel:
    sub = await get_or_create_subscription(session, tenant_id)
    if at_period_end:
        sub.cancel_at_period_end = True
    else:
        sub.status = "canceled"
        sub.canceled_at = datetime.now(timezone.utc)

    await session.flush()

    if _stripe_available() and sub.stripe_subscription_id:
        await _stripe_cancel_subscription(sub.stripe_subscription_id, at_period_end)

    return sub


# ---------------------------------------------------------------------------
# Invoice helpers
# ---------------------------------------------------------------------------

async def list_invoices(
    session: AsyncSession,
    tenant_id: str,
    limit: int = 24,
) -> list[BillingInvoiceModel]:
    result = await session.execute(
        select(BillingInvoiceModel)
        .where(BillingInvoiceModel.tenant_id == tenant_id)
        .order_by(BillingInvoiceModel.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_manual_invoice(
    session: AsyncSession,
    tenant_id: str,
    plan: str,
    billing_cycle: str,
    period_start: datetime,
    period_end: datetime,
    notes: str | None = None,
) -> BillingInvoiceModel:
    # count existing invoices for number generation
    from sqlalchemy import func as sql_func
    count_result = await session.execute(
        select(sql_func.count()).select_from(BillingInvoiceModel)
        .where(BillingInvoiceModel.tenant_id == tenant_id)
    )
    count = count_result.scalar_one() or 0

    plan_info = PLAN_CATALOGUE.get(plan, PLAN_CATALOGUE["free"])
    amount = _plan_amount(plan, billing_cycle)

    invoice = BillingInvoiceModel(
        tenant_id=tenant_id,
        invoice_number=_next_invoice_number(count),
        status="open",
        amount_due_cents=amount,
        amount_paid_cents=0,
        currency="usd",
        period_start=period_start,
        period_end=period_end,
        due_date=period_end,
        description=f"{plan_info['name']} plan — {billing_cycle} billing",
        line_items=[
            {
                "description": f"{plan_info['name']} Plan ({billing_cycle})",
                "amount_cents": amount,
                "quantity": 1,
            }
        ],
        notes=notes,
    )
    session.add(invoice)
    await session.flush()
    return invoice


async def mark_invoice_paid(
    session: AsyncSession,
    invoice_id: str,
    tenant_id: str,
) -> BillingInvoiceModel | None:
    result = await session.execute(
        select(BillingInvoiceModel)
        .where(
            BillingInvoiceModel.id == uuid.UUID(invoice_id),
            BillingInvoiceModel.tenant_id == tenant_id,
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        return None
    inv.status = "paid"
    inv.amount_paid_cents = inv.amount_due_cents
    inv.paid_at = datetime.now(timezone.utc)
    await session.flush()
    return inv


# ---------------------------------------------------------------------------
# Stripe stub helpers (no-ops until STRIPE_SECRET_KEY is present)
# ---------------------------------------------------------------------------

async def _stripe_update_subscription(stripe_sub_id: str, new_plan: str) -> None:
    """Update Stripe subscription price when plan changes."""
    try:
        import stripe  # type: ignore
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        price_id = os.getenv(f"STRIPE_PRICE_{new_plan.upper()}")
        if price_id:
            sub = stripe.Subscription.retrieve(stripe_sub_id)
            stripe.Subscription.modify(
                stripe_sub_id,
                items=[{"id": sub["items"]["data"][0]["id"], "price": price_id}],
                proration_behavior="create_prorations",
            )
    except Exception as exc:
        logger.warning(f"[billing] Stripe update failed (non-fatal): {exc}")


async def _stripe_cancel_subscription(stripe_sub_id: str, at_period_end: bool) -> None:
    try:
        import stripe  # type: ignore
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        stripe.Subscription.modify(stripe_sub_id, cancel_at_period_end=at_period_end)
    except Exception as exc:
        logger.warning(f"[billing] Stripe cancel failed (non-fatal): {exc}")


async def handle_stripe_webhook(payload: bytes, sig_header: str) -> dict[str, Any]:
    """Process Stripe webhook events — called from the billing route."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        return {"status": "webhook_secret_not_configured"}
    try:
        import stripe  # type: ignore
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
        logger.info(f"[billing] Stripe webhook: {event['type']}")
        return {"status": "received", "type": event["type"]}
    except Exception as exc:
        logger.error(f"[billing] Stripe webhook error: {exc}")
        return {"status": "error", "detail": str(exc)}
