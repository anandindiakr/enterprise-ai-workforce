"""HR Applicant Tracker API.

A recruitment pipeline per tenant: add applicants manually or ingest a
resume (LLM extracts name / email / phone / skills and optionally scores
the candidate against a job description). Move applicants through
applied → screening → interview → offer → hired / rejected.

All rows are tenant-scoped.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.logging import logger
from app.db.models import ApplicantModel
from app.db.session import get_db
from app.models.schemas import Principal
from app.security.auth import get_principal

router = APIRouter(prefix="/hr", tags=["hr"])

_PIPELINE = ("applied", "screening", "interview", "offer", "hired", "rejected")


def _serialize(r: ApplicantModel) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "name": r.name,
        "email": r.email,
        "phone": r.phone,
        "position": r.position,
        "status": r.status,
        "score": r.score,
        "skills": r.skills or [],
        "notes": r.notes,
        "resume_doc_id": str(r.resume_doc_id) if r.resume_doc_id else None,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


async def _get_owned(db, applicant_id: str, tenant_id: str | None) -> ApplicantModel:
    try:
        uid = uuid.UUID(applicant_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Applicant not found")
    row = (await db.execute(
        select(ApplicantModel).where(ApplicantModel.id == uid)
    )).scalar_one_or_none()
    if row is None or (row.tenant_id != (tenant_id or "default")):
        raise HTTPException(status_code=404, detail="Applicant not found")
    return row


class ApplicantIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    position: str = Field(default="", max_length=255)
    status: str = Field(default="applied", pattern="^(applied|screening|interview|offer|hired|rejected)$")
    score: int | None = Field(default=None, ge=0, le=100)
    skills: list[str] = Field(default_factory=list)
    notes: str = ""


@router.post("/applicants", status_code=201)
async def create_applicant(
    body: ApplicantIn,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    row = ApplicantModel(
        tenant_id=principal.tenant_id or "default",
        name=body.name.strip(),
        email=(body.email or "").strip().lower() or None,
        phone=(body.phone or "").strip() or None,
        position=body.position.strip(),
        status=body.status,
        score=body.score,
        skills=[s.strip() for s in body.skills if s.strip()][:30],
        notes=body.notes,
        created_by=principal.user_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _serialize(row)


@router.get("/applicants")
async def list_applicants(
    status: str | None = Query(None),
    position: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    q = select(ApplicantModel).where(
        ApplicantModel.tenant_id == (principal.tenant_id or "default")
    )
    if status:
        q = q.where(ApplicantModel.status == status)
    if position:
        q = q.where(ApplicantModel.position.ilike(f"%{position}%"))
    q = q.order_by(ApplicantModel.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    counts: dict[str, int] = {stage: 0 for stage in _PIPELINE}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {"applicants": [_serialize(r) for r in rows], "total": len(rows),
            "pipeline": counts, "stages": list(_PIPELINE)}


@router.patch("/applicants/{applicant_id}")
async def update_applicant(
    applicant_id: str,
    body: dict[str, Any],
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    row = await _get_owned(db, applicant_id, principal.tenant_id)
    allowed = {"name", "email", "phone", "position", "status", "score", "skills", "notes"}
    for field, value in body.items():
        if field == "status" and value not in _PIPELINE:
            raise HTTPException(status_code=422, detail=f"status must be one of {list(_PIPELINE)}")
        if field == "score" and value is not None and not (0 <= int(value) <= 100):
            raise HTTPException(status_code=422, detail="score must be 0-100")
        if field in allowed:
            setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return _serialize(row)


@router.delete("/applicants/{applicant_id}")
async def delete_applicant(
    applicant_id: str,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    row = await _get_owned(db, applicant_id, principal.tenant_id)
    await db.delete(row)
    await db.commit()
    return {"deleted": True, "id": applicant_id}


class IngestResumeIn(BaseModel):
    resume_text: str = Field(..., min_length=40, description="Raw resume text (pasted or extracted)")
    position: str = Field(default="", max_length=255)
    job_description: str | None = Field(default=None, description="Optional JD to score the candidate against")


async def _extract_resume_json(resume_text: str, position: str, jd: str | None) -> dict | None:
    """LLM resume extraction. Returns None when OpenAI isn't configured or
    fails — callers fall back to a manual-review applicant row."""
    from app.core.config import settings

    if not settings.openai_api_key:
        return None
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        score_part = (
            f"\nThen score the candidate's fit for the position on 0-100 "
            f"based on this job description:\n{jd[:3000]}"
            if jd
            else ""
        )
        prompt = (
            "Extract this candidate from the resume text as a JSON object: "
            '{"name": str, "email": str|null, "phone": str|null, '
            '"skills": [str] (max 15), "summary": str (2 sentences)'
            + score_part
            + ". Return ONLY the JSON object.\n\nRESUME:\n" + resume_text[:8000]
        )
        resp = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=800,
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = raw[raw.index("{"): raw.rindex("}") + 1] if "{" in raw and "}" in raw else raw
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Resume extraction failed, using manual-review fallback: {}", exc)
        return None


@router.post("/applicants/ingest", status_code=201)
async def ingest_resume(
    body: IngestResumeIn,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Paste resume text → structured applicant row (+ optional JD fit score).

    Without OPENAI_API_KEY the resume is stored as a manual-review applicant
    so the candidate is never lost.
    """
    data = await _extract_resume_json(body.resume_text, body.position, body.job_description)

    if data:
        score = data.get("score")
        try:
            score = int(score) if score is not None else None
        except (TypeError, ValueError):
            score = None
        row = ApplicantModel(
            tenant_id=principal.tenant_id or "default",
            name=str(data.get("name") or "Unknown candidate")[:255],
            email=(str(data.get("email")).lower() if data.get("email") else None),
            phone=str(data.get("phone")) if data.get("phone") else None,
            position=body.position.strip() or "Unassigned",
            status="screening" if score is not None and score >= 60 else "applied",
            score=score,
            skills=[str(s)[:64] for s in (data.get("skills") or [])][:15],
            notes=str(data.get("summary") or "")[:2000],
            created_by=principal.user_id,
            metadata_={"ingested": True},
        )
    else:
        row = ApplicantModel(
            tenant_id=principal.tenant_id or "default",
            name="Unknown candidate",
            position=body.position.strip() or "Unassigned",
            status="applied",
            notes=body.resume_text[:2000],
            created_by=principal.user_id,
            metadata_={"ingested": True, "extraction": "unavailable"},
        )

    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "applicant": _serialize(row),
        "extraction": "llm" if data else "pending_review",
    }
