"""Billing & invoicing API routes.

Endpoints:
  GET    /billing/plans                         — plan catalogue (public)
  GET    /tenants/{slug}/billing                — subscription + invoices summary
  POST   /tenants/{slug}/billing/subscribe      — create / change subscription
  DELETE /tenants/{slug}/billing/cancel         — cancel subscription
  GET    /tenants/{slug}/billing/invoices       — list invoices
  POST   /tenants/{slug}/billing/invoices       — create manual invoice (admin)
  PATCH  /tenants/{slug}/billing/invoices/{id}/pay — mark invoice paid (admin)
  POST   /billing/webhooks/stripe               — Stripe webhook receiver
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import require_roles
from app.services import billing_service as svc

router = APIRouter(prefix="/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SubscribeRequest(BaseModel):
    plan: str = "starter"
    billing_cycle: str = "monthly"   # monthly | annual


class CancelRequest(BaseModel):
    at_period_end: bool = True


class CreateInvoiceRequest(BaseModel):
    plan: str
    billing_cycle: str = "monthly"
    period_start: datetime | None = None
    period_end: datetime | None = None
    notes: str | None = None


def _fmt_sub(sub: Any) -> dict:
    return {
        "id": str(sub.id),
        "tenant_id": sub.tenant_id,
        "plan": sub.plan,
        "status": sub.status,
        "billing_cycle": sub.billing_cycle,
        "currency": sub.currency,
        "amount_cents": sub.amount_cents,
        "amount_display": f"${sub.amount_cents / 100:.2f}",
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "trial_end": sub.trial_end.isoformat() if sub.trial_end else None,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "canceled_at": sub.canceled_at.isoformat() if sub.canceled_at else None,
        "stripe_customer_id": sub.stripe_customer_id,
        "stripe_subscription_id": sub.stripe_subscription_id,
        "stripe_connected": bool(sub.stripe_customer_id),
        "created_at": sub.created_at.isoformat(),
    }


def _fmt_inv(inv: Any) -> dict:
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "tenant_id": inv.tenant_id,
        "status": inv.status,
        "amount_due_cents": inv.amount_due_cents,
        "amount_paid_cents": inv.amount_paid_cents,
        "amount_due_display": f"${inv.amount_due_cents / 100:.2f}",
        "currency": inv.currency,
        "description": inv.description,
        "period_start": inv.period_start.isoformat() if inv.period_start else None,
        "period_end": inv.period_end.isoformat() if inv.period_end else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        "line_items": inv.line_items,
        "pdf_url": inv.pdf_url,
        "hosted_invoice_url": inv.hosted_invoice_url,
        "notes": inv.notes,
        "stripe_invoice_id": inv.stripe_invoice_id,
        "created_at": inv.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Public plan catalogue
# ---------------------------------------------------------------------------

@router.get("/plans")
async def get_plans() -> dict:
    """Return the plan catalogue — no auth needed so signup flows can read it."""
    plans = []
    for key, info in svc.PLAN_CATALOGUE.items():
        plans.append({
            "key": key,
            "name": info["name"],
            "amount_cents_monthly": info["amount_cents"],
            "amount_cents_annual": int(info["amount_cents"] * 12 * (1 - svc.ANNUAL_DISCOUNT_PCT / 100)),
            "amount_display_monthly": f"${info['amount_cents'] / 100:.0f}/mo",
            "amount_display_annual": f"${info['amount_cents'] * 12 * (1 - svc.ANNUAL_DISCOUNT_PCT / 100) / 100:.0f}/yr",
            "annual_discount_pct": svc.ANNUAL_DISCOUNT_PCT,
            "max_users": info["max_users"],
            "max_chat_sessions": info["max_chat_sessions"],
            "max_voice_minutes": info["max_voice_minutes"],
            "features": info["features"],
        })
    return {
        "plans": plans,
        "stripe_available": svc._stripe_available(),
        "annual_discount_pct": svc.ANNUAL_DISCOUNT_PCT,
    }


# ---------------------------------------------------------------------------
# Per-tenant billing endpoints (admin only)
# ---------------------------------------------------------------------------

@router.get("/tenants/{slug}/billing")
async def get_billing(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_roles("admin")),
) -> dict:
    sub = await svc.get_or_create_subscription(db, slug)
    invoices = await svc.list_invoices(db, slug, limit=5)
    await db.commit()
    return {
        "subscription": _fmt_sub(sub),
        "recent_invoices": [_fmt_inv(i) for i in invoices],
        "plan_info": svc.PLAN_CATALOGUE.get(sub.plan, svc.PLAN_CATALOGUE["free"]),
    }


@router.post("/tenants/{slug}/billing/subscribe", status_code=status.HTTP_200_OK)
async def subscribe(
    slug: str,
    body: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_roles("admin")),
) -> dict:
    if body.plan not in svc.PLAN_CATALOGUE:
        raise HTTPException(400, f"Unknown plan '{body.plan}'. Valid: {list(svc.PLAN_CATALOGUE)}")
    if body.billing_cycle not in ("monthly", "annual"):
        raise HTTPException(400, "billing_cycle must be 'monthly' or 'annual'")

    sub = await svc.change_plan(db, slug, body.plan, body.billing_cycle)
    await db.commit()
    return {"subscription": _fmt_sub(sub), "message": f"Plan updated to '{body.plan}'"}


@router.delete("/tenants/{slug}/billing/cancel")
async def cancel(
    slug: str,
    body: CancelRequest = CancelRequest(),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_roles("admin")),
) -> dict:
    sub = await svc.cancel_subscription(db, slug, body.at_period_end)
    await db.commit()
    msg = "Subscription will cancel at period end." if body.at_period_end else "Subscription canceled immediately."
    return {"subscription": _fmt_sub(sub), "message": msg}


@router.get("/tenants/{slug}/billing/invoices")
async def get_invoices(
    slug: str,
    limit: int = 24,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_roles("admin")),
) -> dict:
    invoices = await svc.list_invoices(db, slug, limit=limit)
    return {
        "invoices": [_fmt_inv(i) for i in invoices],
        "total": len(invoices),
    }


@router.post("/tenants/{slug}/billing/invoices", status_code=status.HTTP_201_CREATED)
async def create_invoice(
    slug: str,
    body: CreateInvoiceRequest,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_roles("admin")),
) -> dict:
    now = datetime.now(timezone.utc)
    period_start = body.period_start or now.replace(day=1)
    period_end = body.period_end or (now + timedelta(days=30))

    inv = await svc.create_manual_invoice(
        db, slug, body.plan, body.billing_cycle,
        period_start, period_end, body.notes,
    )
    await db.commit()
    return {"invoice": _fmt_inv(inv)}


@router.patch("/tenants/{slug}/billing/invoices/{invoice_id}/pay")
async def pay_invoice(
    slug: str,
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(require_roles("admin")),
) -> dict:
    inv = await svc.mark_invoice_paid(db, invoice_id, slug)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    await db.commit()
    return {"invoice": _fmt_inv(inv), "message": "Invoice marked as paid"}


# ---------------------------------------------------------------------------
# Stripe webhook (no auth — verified by Stripe signature)
# ---------------------------------------------------------------------------

@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    result = await svc.handle_stripe_webhook(payload, sig)
    # TODO: handle specific event types (invoice.paid, subscription.updated, etc.)
    # and update local DB records to stay in sync with Stripe
    return result
