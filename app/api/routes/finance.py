"""Finance Ledger API.

Turns the Finance agent from a chat-only assistant into a bookkeeping tool:
- manual ledger entries (invoices in, expenses out, payments),
- bill/invoice ingestion: paste bill text (or upload-extracted text) and an
  LLM extracts vendor / amount / date / type into structured ledger rows,
- monthly + category summaries, CSV export, and emailing the report
  (real send via Resend/SMTP when configured, honest error when not).

All rows are tenant-scoped: every organisation's books are isolated.
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.logging import logger
from app.db.models import LedgerEntryModel
from app.db.session import get_db
from app.models.schemas import Principal
from app.security.auth import get_principal

router = APIRouter(prefix="/finance", tags=["finance"])

_VALID_TYPES = {"invoice", "expense", "payment"}
_VALID_STATUS = {"recorded", "pending_review", "paid"}


def _serialize(r: LedgerEntryModel) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "entry_date": r.entry_date.isoformat(),
        "entry_type": r.entry_type,
        "vendor": r.vendor,
        "description": r.description,
        "amount": r.amount,
        "currency": r.currency,
        "category": r.category,
        "status": r.status,
        "source_doc": r.source_doc,
        "created_by": r.created_by,
        "created_at": r.created_at.isoformat(),
    }


async def _get_owned(db, entry_id: str, tenant_id: str | None) -> LedgerEntryModel:
    try:
        uid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Ledger entry not found")
    row = (await db.execute(
        select(LedgerEntryModel).where(LedgerEntryModel.id == uid)
    )).scalar_one_or_none()
    if row is None or (row.tenant_id != (tenant_id or "default")):
        raise HTTPException(status_code=404, detail="Ledger entry not found")
    return row


class LedgerIn(BaseModel):
    entry_type: str = Field(default="expense", pattern="^(invoice|expense|payment)$")
    vendor: str = ""
    description: str = ""
    amount: float = Field(..., gt=0)
    currency: str = "INR"
    category: str | None = None
    entry_date: datetime | None = None
    source_doc: str | None = None


@router.post("/ledger", status_code=201)
async def create_entry(
    body: LedgerIn,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    row = LedgerEntryModel(
        tenant_id=principal.tenant_id or "default",
        entry_type=body.entry_type,
        vendor=body.vendor.strip(),
        description=body.description.strip(),
        amount=body.amount,
        currency=body.currency.strip().upper()[:8] or "INR",
        category=(body.category or "").strip() or None,
        entry_date=body.entry_date or datetime.now(timezone.utc),
        source_doc=body.source_doc,
        created_by=principal.user_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _serialize(row)


@router.get("/ledger")
async def list_entries(
    entry_type: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    q = select(LedgerEntryModel).where(
        LedgerEntryModel.tenant_id == (principal.tenant_id or "default")
    )
    if entry_type:
        q = q.where(LedgerEntryModel.entry_type == entry_type)
    if category:
        q = q.where(LedgerEntryModel.category == category)
    q = q.order_by(LedgerEntryModel.entry_date.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return {"entries": [_serialize(r) for r in rows], "total": len(rows)}


@router.patch("/ledger/{entry_id}")
async def update_entry(
    entry_id: str,
    body: dict[str, Any],
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    row = await _get_owned(db, entry_id, principal.tenant_id)
    allowed = {"entry_type", "vendor", "description", "amount", "currency",
               "category", "status", "entry_date"}
    for field, value in body.items():
        if field == "entry_type" and value not in _VALID_TYPES:
            raise HTTPException(status_code=422, detail=f"entry_type must be one of {sorted(_VALID_TYPES)}")
        if field == "status" and value not in _VALID_STATUS:
            raise HTTPException(status_code=422, detail=f"status must be one of {sorted(_VALID_STATUS)}")
        if field in allowed:
            setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return _serialize(row)


@router.delete("/ledger/{entry_id}")
async def delete_entry(
    entry_id: str,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    row = await _get_owned(db, entry_id, principal.tenant_id)
    await db.delete(row)
    await db.commit()
    return {"deleted": True, "id": entry_id}


@router.get("/ledger/summary")
async def ledger_summary(
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    tenant = principal.tenant_id or "default"

    def _agg(row) -> dict:
        return {"type": row[0], "total": float(row[1] or 0), "count": row[2]}

    rows = (await db.execute(
        select(LedgerEntryModel.entry_type, func.sum(LedgerEntryModel.amount),
               func.count(LedgerEntryModel.id))
        .where(LedgerEntryModel.tenant_id == tenant)
        .group_by(LedgerEntryModel.entry_type)
    )).all()
    by_type = {_agg(r)["type"]: _agg(r) for r in rows}

    by_category_rows = (await db.execute(
        select(LedgerEntryModel.category, func.sum(LedgerEntryModel.amount))
        .where(LedgerEntryModel.tenant_id == tenant)
        .group_by(LedgerEntryModel.category)
    )).all()

    total_in = by_type.get("invoice", {}).get("total", 0.0)
    total_out = by_type.get("expense", {}).get("total", 0.0)
    return {
        "total_invoiced": total_in,
        "total_expenses": total_out,
        "net": round(total_in - total_out, 2),
        "payments_recorded": by_type.get("payment", {}).get("total", 0.0),
        "by_type": [_agg(r) for r in rows],
        "by_category": [
            {"category": r[0] or "Uncategorised", "total": float(r[1] or 0)}
            for r in by_category_rows
        ],
        "count": sum(r[2] for r in rows),
    }


@router.get("/ledger/export.csv")
async def export_csv(
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> Response:
    q = select(LedgerEntryModel).where(
        LedgerEntryModel.tenant_id == (principal.tenant_id or "default")
    ).order_by(LedgerEntryModel.entry_date.desc())
    rows = (await db.execute(q)).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "type", "vendor", "description", "amount", "currency",
                     "category", "status", "source"])
    for r in rows:
        writer.writerow([
            r.entry_date.strftime("%Y-%m-%d"), r.entry_type, r.vendor,
            r.description.replace("\n", " "), r.amount, r.currency,
            r.category or "", r.status, r.source_doc or "",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ledger.csv"'},
    )


class IngestIn(BaseModel):
    text: str = Field(..., min_length=20, description="Raw bill/invoice text (pasted or OCR'd)")
    source_doc: str | None = Field(default=None, max_length=255)


async def _extract_bill_json(text: str) -> list[dict] | None:
    """LLM extraction of ledger fields from bill text. Returns None when no
    OpenAI key is configured or the call fails — callers fall back to a
    pending-review entry so nothing is ever silently lost."""
    from app.core.config import settings

    api_key = settings.openai_api_key
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        prompt = (
            "Extract every line item from this bill/invoice text as a JSON array. "
            "Each item: {\"entry_type\": \"expense\"|\"invoice\"|\"payment\", "
            "\"vendor\": str, \"description\": str, \"amount\": number>0, "
            "\"currency\": str (default INR), \"category\": str (e.g. utilities, "
            "software, travel, salary, rent, office), \"date\": \"YYYY-MM-DD\"}. "
            "Return ONLY the JSON array, no prose.\n\nBILL TEXT:\n" + text[:8000]
        )
        resp = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1500,
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = raw[raw.index("["): raw.rindex("]") + 1] if "[" in raw and "]" in raw else raw
        items = json.loads(raw)
        return items if isinstance(items, list) and items else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Bill extraction failed, using pending-review fallback: {}", exc)
        return None


@router.post("/ledger/ingest", status_code=201)
async def ingest_bill(
    body: IngestIn,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Paste bill/invoice text → structured ledger entries.

    With OPENAI_API_KEY set, an LLM extracts structured rows. Without it,
    the bill is stored as one pending_review entry so the data is never
    lost and can be fixed by hand.
    """
    tenant = principal.tenant_id or "default"
    items = await _extract_bill_json(body.text)

    created: list[dict] = []
    if items:
        for it in items:
            try:
                amount = float(it.get("amount") or 0)
            except (TypeError, ValueError):
                continue
            if amount <= 0:
                continue
            entry_type = str(it.get("entry_type") or "expense").lower()
            if entry_type not in _VALID_TYPES:
                entry_type = "expense"
            entry_date = datetime.now(timezone.utc)
            try:
                if it.get("date"):
                    entry_date = datetime.fromisoformat(str(it["date"]))
            except ValueError:
                pass
            row = LedgerEntryModel(
                tenant_id=tenant,
                entry_type=entry_type,
                vendor=str(it.get("vendor") or "")[:255],
                description=str(it.get("description") or "")[:2000],
                amount=amount,
                currency=str(it.get("currency") or "INR").upper()[:8],
                category=str(it.get("category") or "").lower()[:64] or None,
                entry_date=entry_date,
                status="recorded",
                source_doc=body.source_doc,
                created_by=principal.user_id,
                metadata_={"ingested": True},
            )
            db.add(row)
            created.append(row)
        await db.commit()
        for r in created:
            await db.refresh(r)

    if not created:
        fallback = LedgerEntryModel(
            tenant_id=tenant,
            entry_type="expense",
            vendor="",
            description=body.text[:2000],
            amount=0.0,
            status="pending_review",
            source_doc=body.source_doc,
            created_by=principal.user_id,
            metadata_={"ingested": True, "extraction": "unavailable"},
        )
        # amount is non-negative by validation; store the raw text for review
        fallback.amount = 0.0
        db.add(fallback)
        await db.commit()
        await db.refresh(fallback)
        created = [fallback]

    return {
        "created": [_serialize(r) for r in created],
        "extraction": "llm" if items else "pending_review",
        "count": len(created),
    }


class EmailReportIn(BaseModel):
    to: str = Field(..., pattern="^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")


@router.post("/ledger/email")
async def email_report(
    body: EmailReportIn,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Email the ledger summary to a recipient (Resend/SMTP when configured)."""
    summary = await ledger_summary(principal=principal, db=db)
    lines = [
        "Finance Ledger Summary",
        "======================",
        f"Total invoiced : {summary['total_invoiced']:,.2f}",
        f"Total expenses : {summary['total_expenses']:,.2f}",
        f"Net            : {summary['net']:,.2f}",
        f"Entries        : {summary['count']}",
        "",
        "By category:",
    ]
    lines += [f"  - {c['category']}: {c['total']:,.2f}" for c in summary["by_category"]]
    from app.services.notification_service import send_generic_email

    result = await send_generic_email(
        body.to, "AI Workforce — Finance Ledger Summary", "\n".join(lines)
    )
    if not result.get("sent"):
        raise HTTPException(
            status_code=503,
            detail="Email provider not configured or send failed. Add RESEND_API_KEY "
                   "(or SMTP_HOST/SMTP_USER/SMTP_PASSWORD) to the server environment.",
        )
    return {"sent": True, "provider": result.get("provider"), "to": body.to}
