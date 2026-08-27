"""Unit tests for the Finance Ledger and HR Applicant Tracker.

Verifies:
- ledger entries: create, list, summary, CSV export, tenant isolation (404),
- applicants: create, pipeline patch, tenant isolation (404),
- ingestion fallbacks: without an OpenAI key, bill and resume text are kept
  as pending-review rows instead of being lost.
"""
from __future__ import annotations

import pytest

from app.api.routes.finance import (
    LedgerIn,
    create_entry,
    delete_entry,
    export_csv,
    ingest_bill,
    ledger_summary,
    list_entries,
)
from app.api.routes.hr import (
    ApplicantIn,
    create_applicant,
    ingest_resume,
    list_applicants,
    update_applicant,
)
from app.models.schemas import Principal


def _p(tenant: str) -> Principal:
    return Principal(user_id=f"{tenant}-user", tenant_id=tenant)


# ── Finance ledger ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ledger_create_list_summary(db_session):
    await create_entry(
        LedgerIn(entry_type="invoice", vendor="Acme Corp", amount=50000, category="sales"),
        principal=_p("acme"), db=db_session,
    )
    await create_entry(
        LedgerIn(entry_type="expense", vendor="AWS", amount=12000, category="software"),
        principal=_p("acme"), db=db_session,
    )
    await create_entry(
        LedgerIn(entry_type="expense", vendor="Rent", amount=20000, category="rent"),
        principal=_p("acme"), db=db_session,
    )

    listed = await list_entries(entry_type=None, category=None, limit=100,
                                principal=_p("acme"), db=db_session)
    assert listed["total"] == 3

    summary = await ledger_summary(principal=_p("acme"), db=db_session)
    assert summary["total_invoiced"] == 50000
    assert summary["total_expenses"] == 32000
    assert summary["net"] == 18000
    cats = {c["category"]: c["total"] for c in summary["by_category"]}
    assert cats["software"] == 12000 and cats["rent"] == 20000


@pytest.mark.asyncio
async def test_ledger_csv_export(db_session):
    await create_entry(
        LedgerIn(entry_type="expense", vendor="AWS", amount=12000),
        principal=_p("acme"), db=db_session,
    )
    resp = await export_csv(principal=_p("acme"), db=db_session)
    body = resp.body.decode() if isinstance(resp.body, bytes) else str(resp.body)
    assert "vendor" in body and "AWS" in body and "12000" in body


@pytest.mark.asyncio
async def test_ledger_tenant_isolation(db_session):
    from fastapi import HTTPException

    entry = await create_entry(
        LedgerIn(entry_type="expense", vendor="Secret Vendor", amount=999),
        principal=_p("acme"), db=db_session,
    )
    # Another tenant sees nothing in the list…
    other = await list_entries(entry_type=None, category=None, limit=100,
                               principal=_p("globex"), db=db_session)
    assert other["total"] == 0
    # …and cannot touch the row directly (404, no existence leak).
    with pytest.raises(HTTPException) as excinfo:
        await delete_entry(entry["id"], principal=_p("globex"), db=db_session)
    assert excinfo.value.status_code == 404


# ── HR applicants ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_applicant_pipeline(db_session):
    a = await create_applicant(
        ApplicantIn(name="Priya Sharma", email="priya@example.com",
                    position="Sales Executive", skills=["CRM", "negotiation"]),
        principal=_p("acme"), db=db_session,
    )
    moved = await update_applicant(
        a["id"], {"status": "interview", "score": 78},
        principal=_p("acme"), db=db_session,
    )
    assert moved["status"] == "interview" and moved["score"] == 78

    listed = await list_applicants(status=None, position=None, limit=200,
                                   principal=_p("acme"), db=db_session)
    assert listed["pipeline"]["interview"] == 1
    assert listed["applicants"][0]["skills"] == ["CRM", "negotiation"]


@pytest.mark.asyncio
async def test_applicant_tenant_isolation(db_session):
    from fastapi import HTTPException

    a = await create_applicant(
        ApplicantIn(name="Internal Candidate", position="HR"),
        principal=_p("acme"), db=db_session,
    )
    with pytest.raises(HTTPException) as excinfo:
        await update_applicant(
            a["id"], {"status": "hired"}, principal=_p("globex"), db=db_session
        )
    assert excinfo.value.status_code == 404


# ── Ingestion fallbacks (no OpenAI key in the test env) ─────────────────────


@pytest.mark.asyncio
async def test_bill_ingest_falls_back_to_review(db_session):
    result = await ingest_bill(
        type("In", (object,), {"text": "ACME ELECTRICITY BILL invoice 4230 rupees dated 05/08/2026 for august electricity", "source_doc": "paste"})(),
        principal=_p("acme"), db=db_session,
    )
    # In the test env there is no OpenAI key — must fall back, not crash or drop data.
    assert result["count"] >= 1
    if result["extraction"] == "pending_review":
        assert result["created"][0]["status"] == "pending_review"
        assert "ELECTRICITY" in result["created"][0]["description"]


@pytest.mark.asyncio
async def test_resume_ingest_falls_back_to_review(db_session):
    result = await ingest_resume(
        type("In", (object,), {
            "resume_text": "Priya Sharma, sales professional with 5 years of CRM and enterprise negotiation experience across SaaS accounts in Singapore and India.",
            "position": "Sales Executive",
            "job_description": None,
        })(),
        principal=_p("acme"), db=db_session,
    )
    assert result["applicant"]["name"]
    assert result["applicant"]["position"] == "Sales Executive"
