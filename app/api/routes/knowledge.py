"""File upload and knowledge-base management API.

POST /api/v1/knowledge/upload  — upload a document (txt/pdf/docx)
GET  /api/v1/knowledge/        — list documents
GET  /api/v1/knowledge/{id}    — get single document
DELETE /api/v1/knowledge/{id}  — delete document
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logging import logger
from app.db.crud import create_knowledge_document, list_knowledge_documents
from app.db.session import get_db
from app.models.schemas import Principal
from app.security.auth import get_principal

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_ALLOWED_MIME = {
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown",
    "text/csv",
    "application/json",
}


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    category: str = Form("General"),
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict[str, Any]:
    """Upload a document to the knowledge base.

    Supported types: .txt, .md, .csv, .json, .pdf, .docx
    Max size: ``MAX_UPLOAD_SIZE_MB`` (default 20 MB).
    """
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    raw = await file.read()
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )

    content = _extract_text(raw, file.filename or "", file.content_type or "")
    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract text from the uploaded file",
        )

    doc_title = title or Path(file.filename or "document").stem
    doc = await create_knowledge_document(
        db,
        tenant_id=principal.tenant_id or "default",
        title=doc_title,
        category=category,
        content=content,
        file_name=file.filename,
        file_size=len(raw),
        mime_type=file.content_type,
        uploaded_by=principal.user_id,
    )

    # Kick off async embedding via Celery (fire-and-forget)
    try:
        from app.workers.tasks import ingest_document
        ingest_document.delay(
            str(doc.id),
            content,
            {"title": doc_title, "category": category, "tenant_id": doc.tenant_id},
        )
    except Exception:  # noqa: BLE001
        pass

    logger.info("Knowledge doc uploaded: {} ({} bytes)", doc.id, len(raw))
    return {
        "id": str(doc.id),
        "title": doc.title,
        "category": doc.category,
        "file_name": doc.file_name,
        "file_size": doc.file_size,
        "embedding_status": doc.embedding_status,
        "created_at": doc.created_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
@router.get("/")
async def list_documents(
    category: str | None = None,
    skip: int = 0,
    limit: int = 50,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict[str, Any]:
    docs = await list_knowledge_documents(
        db,
        tenant_id=principal.tenant_id or "default",
        category=category,
        skip=skip,
        limit=limit,
    )
    return {
        "documents": [
            {
                "id": str(d.id),
                "title": d.title,
                "category": d.category,
                "file_name": d.file_name,
                "file_size": d.file_size,
                "embedding_status": d.embedding_status,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
        "total": len(docs),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Get single
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict[str, Any]:
    from sqlalchemy import select
    from app.db.models import KnowledgeDocumentModel
    try:
        did = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.execute(
        select(KnowledgeDocumentModel).where(
            KnowledgeDocumentModel.id == did,
            KnowledgeDocumentModel.tenant_id == (principal.tenant_id or "default"),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": str(doc.id),
        "title": doc.title,
        "category": doc.category,
        "content": doc.content[:2000],  # truncated preview
        "file_name": doc.file_name,
        "file_size": doc.file_size,
        "embedding_status": doc.embedding_status,
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Delete
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> None:
    from sqlalchemy import select
    from app.db.models import KnowledgeDocumentModel
    try:
        did = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.execute(
        select(KnowledgeDocumentModel).where(
            KnowledgeDocumentModel.id == did,
            KnowledgeDocumentModel.tenant_id == (principal.tenant_id or "default"),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)


# ─────────────────────────────────────────────────────────────────────────────
# Text extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text(raw: bytes, filename: str, mime: str) -> str:
    """Best-effort text extraction from uploaded file bytes."""
    ext = Path(filename).suffix.lower()

    # Plain text / markdown / CSV / JSON
    if ext in (".txt", ".md", ".csv", ".json") or "text/" in mime:
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return ""

    # PDF — use pdfplumber if available, otherwise raw decode
    if ext == ".pdf" or mime == "application/pdf":
        try:
            import io
            import pdfplumber  # type: ignore
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                return "\n".join(
                    (p.extract_text() or "") for p in pdf.pages
                )
        except ImportError:
            pass
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return ""

    # DOCX — use python-docx if available
    if ext in (".docx",) or "wordprocessingml" in mime:
        try:
            import io
            from docx import Document  # type: ignore
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        except ImportError:
            pass

    # Fallback: try UTF-8
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""
