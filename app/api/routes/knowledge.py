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

# Hard references to in-flight background embedding tasks (prevents GC).
_EMBED_TASKS: set = set()


# ─────────────────────────────────────────────────────────────────────────────
# Semantic search
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import Query as _Query

@router.get("/search")
async def search_knowledge(
    q: str = _Query(..., min_length=1, description="Natural-language search query"),
    top_k: int = _Query(5, ge=1, le=20),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Semantic search over the knowledge base using ChromaDB vector similarity."""
    try:
        from app.memory.long_term import long_term_memory
        mem = long_term_memory()
        results = mem.search(q, k=top_k)
        return {"query": q, "results": results, "count": len(results)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Knowledge search failed: {}", exc)
        return {"query": q, "results": [], "count": 0, "error": str(exc)}

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

    # Kick off embedding.  By default we embed in-process via an asyncio task
    # so the knowledge base works without a running Celery worker.  Celery is
    # only used when explicitly enabled (settings.use_celery) AND a worker is
    # available; otherwise documents would stay "pending" forever.
    _meta = {"title": doc_title, "category": category, "tenant_id": doc.tenant_id}
    _dispatched = False
    if settings.use_celery:
        try:
            from app.workers.tasks import ingest_document
            ingest_document.delay(str(doc.id), content, _meta)
            _dispatched = True
        except Exception:  # noqa: BLE001
            _dispatched = False

    if not _dispatched:
        import asyncio
        # Keep a hard reference to the background task. asyncio only holds a
        # weak reference, so without this the embedding task can be
        # garbage-collected mid-flight, leaving the doc stuck at "pending".
        _task = asyncio.create_task(_embed_document(str(doc.id), content, _meta))
        _EMBED_TASKS.add(_task)
        _task.add_done_callback(_EMBED_TASKS.discard)

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


# ─────────────────────────────────────────────────────────────────────────────
# Background embedding helper (asyncio fallback when Celery is unavailable)
# ─────────────────────────────────────────────────────────────────────────────

async def _embed_document(doc_id: str, content: str, metadata: dict) -> None:
    """Embed and store a document in ChromaDB; update DB embedding_status.

    Runs in an asyncio background task.  Creates its own DB session so it is
    not affected by the already-closed request session.
    """
    try:
        import asyncio as _asyncio
        from app.memory.long_term import long_term_memory

        mem = long_term_memory()
        # ChromaDB upsert is blocking — run it in a thread to avoid blocking
        # the event loop while sentence-transformers generates embeddings.
        loop = _asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: mem.upsert(content, doc_id=doc_id, metadata=metadata)
        )

        # Update embedding status using a fresh independent DB session
        import uuid as _uuid
        from sqlalchemy import update as _update
        from app.db.models import KnowledgeDocumentModel
        from app.db.session import AsyncSessionLocal

        try:
            did = _uuid.UUID(doc_id)
            async with AsyncSessionLocal() as new_db:
                await new_db.execute(
                    _update(KnowledgeDocumentModel)
                    .where(KnowledgeDocumentModel.id == did)
                    .values(embedding_status="complete")
                )
                await new_db.commit()
        except Exception:  # noqa: BLE001
            pass  # status update is best-effort

        logger.info("Knowledge doc embedded (asyncio fallback): {}", doc_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Knowledge embedding failed for {}: {}", doc_id, exc)
        # Mark as failed so the UI does not hang forever on "pending".
        try:
            import uuid as _uuid2
            from sqlalchemy import update as _update2
            from app.db.models import KnowledgeDocumentModel as _KDM
            from app.db.session import AsyncSessionLocal as _ASL

            async with _ASL() as _db:
                await _db.execute(
                    _update2(_KDM)
                    .where(_KDM.id == _uuid2.UUID(doc_id))
                    .values(embedding_status="failed")
                )
                await _db.commit()
        except Exception:  # noqa: BLE001
            pass
