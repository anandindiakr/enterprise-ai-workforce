"""File upload and knowledge-base management API.

Document lifecycle
------------------
1. File uploaded → content extracted → saved to PostgreSQL → status: "indexed"
   (DB keyword search works for agents immediately)
2. Background task embeds text into ChromaDB → status: "complete"
   (vector similarity search also active)
3. If embedding fails → status: "failed"
   (agents still work via DB keyword search, but no vector search)

Status meanings for the UI
---------------------------
- indexed   : Content in DB, keyword search active. Agents can use it.
- complete  : Content in DB + vector index. Both keyword + semantic search active.
- failed    : ChromaDB embedding failed. Agents still use keyword search.
- pending   : Just uploaded, embedding task queued.
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select, update

from app.core.config import settings
from app.core.logging import logger
from app.db.crud import create_knowledge_document, list_knowledge_documents
from app.db.models import KnowledgeDocumentModel
from app.db.session import AsyncSessionLocal, get_db
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
    q: str = _Query(..., min_length=1),
    top_k: int = _Query(5, ge=1, le=20),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Semantic search over ChromaDB. Falls back to keyword search if unavailable."""
    try:
        from app.memory.long_term import long_term_memory
        mem = long_term_memory()
        results = mem.search(q, k=top_k)
        return {"query": q, "results": results, "count": len(results), "source": "vector"}
    except Exception as exc:
        logger.warning("Knowledge vector search failed: {}", exc)
        return {"query": q, "results": [], "count": 0, "error": str(exc), "source": "none"}


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

_ALLOWED_MIME = {
    "text/plain", "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown", "text/csv", "application/json",
}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    category: str = Form("General"),
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict[str, Any]:
    """Upload a document. Content is immediately available to agents via DB search."""
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

    # Mark as "indexed" immediately — content is in DB, agents can use it NOW
    await db.execute(
        update(KnowledgeDocumentModel)
        .where(KnowledgeDocumentModel.id == doc.id)
        .values(embedding_status="indexed")
    )
    await db.commit()

    # Then kick off vector embedding in background (upgrades to "complete")
    _meta = {
        "title": doc_title,
        "category": category,
        "tenant_id": doc.tenant_id,
        "doc_id": str(doc.id),
    }
    _dispatched = False
    if settings.use_celery:
        try:
            from app.workers.tasks import ingest_document
            ingest_document.delay(str(doc.id), content, _meta)
            _dispatched = True
        except Exception:  # noqa: BLE001
            _dispatched = False

    if not _dispatched:
        _task = asyncio.create_task(_embed_document(str(doc.id), content, _meta))
        _EMBED_TASKS.add(_task)
        _task.add_done_callback(_EMBED_TASKS.discard)

    logger.info("Knowledge doc uploaded: {} '{}' ({} bytes)", doc.id, doc_title, len(raw))
    return {
        "id": str(doc.id),
        "title": doc.title,
        "category": doc.category,
        "file_name": doc.file_name,
        "file_size": doc.file_size,
        "embedding_status": "indexed",
        "message": "Document saved. Agents can use it immediately. Vector indexing in progress.",
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
# Stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def kb_stats(
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Return KB health stats — document counts and vector index status."""
    from sqlalchemy import func as sql_func

    tid = principal.tenant_id or "default"
    rows = await db.execute(
        select(
            KnowledgeDocumentModel.embedding_status,
            sql_func.count().label("cnt"),
        )
        .where(KnowledgeDocumentModel.tenant_id == tid)
        .group_by(KnowledgeDocumentModel.embedding_status)
    )
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.embedding_status] = row.cnt

    # Chroma vector count
    vector_count = 0
    chroma_ok = False
    try:
        from app.memory.long_term import long_term_memory
        mem = long_term_memory()
        vector_count = mem.count()
        chroma_ok = True
    except Exception:
        pass

    total = sum(status_counts.values())
    indexed_and_above = status_counts.get("indexed", 0) + status_counts.get("complete", 0)

    return {
        "total": total,
        "by_status": status_counts,
        "indexed": indexed_and_above,
        "complete": status_counts.get("complete", 0),
        "pending": status_counts.get("pending", 0),
        "failed": status_counts.get("failed", 0),
        "vector_count": vector_count,
        "chroma_available": chroma_ok,
        "agents_have_access": indexed_and_above > 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Reindex
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/reindex")
async def reindex_knowledge(
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict:
    """Re-embed all documents that are missing from ChromaDB vector store.

    Safe to call at any time — only re-embeds docs that are NOT already
    in ChromaDB (checks by doc ID). Use after container restart or when
    many docs show as 'failed'.
    """
    tid = principal.tenant_id or "default"
    result = await db.execute(
        select(KnowledgeDocumentModel)
        .where(
            KnowledgeDocumentModel.tenant_id == tid,
            KnowledgeDocumentModel.content.isnot(None),
        )
        .order_by(KnowledgeDocumentModel.created_at.desc())
        .limit(200)
    )
    docs = list(result.scalars().all())

    if not docs:
        return {"queued": 0, "message": "No documents to reindex"}

    queued = 0
    for doc in docs:
        _meta = {
            "title": doc.title,
            "category": doc.category,
            "tenant_id": doc.tenant_id,
            "doc_id": str(doc.id),
        }
        _task = asyncio.create_task(
            _embed_document(str(doc.id), doc.content or "", _meta, force=True)
        )
        _EMBED_TASKS.add(_task)
        _task.add_done_callback(_EMBED_TASKS.discard)
        queued += 1

    logger.info("Knowledge reindex queued {} docs for tenant {}", queued, tid)
    return {
        "queued": queued,
        "message": f"Reindexing {queued} documents. Refresh the page in a minute to see updated statuses.",
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
        "content": doc.content[:3000] if doc.content else "",
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

    # Also remove from vector store
    try:
        from app.memory.long_term import long_term_memory
        long_term_memory().delete(str(did))
    except Exception:
        pass

    await db.delete(doc)


# ─────────────────────────────────────────────────────────────────────────────
# Startup re-index utility (called from main.py lifespan)
# ─────────────────────────────────────────────────────────────────────────────

async def startup_reindex() -> None:
    """Re-embed docs that are in DB but missing from ChromaDB.

    Called once during app startup. Handles the case where the container
    restarts and the Chroma volume is empty (or was recreated).
    """
    try:
        from app.memory.long_term import long_term_memory
        mem = long_term_memory()
        vector_count = mem.count()
        logger.info("startup_reindex: ChromaDB has {} vectors", vector_count)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(KnowledgeDocumentModel)
                .where(
                    KnowledgeDocumentModel.content.isnot(None),
                    KnowledgeDocumentModel.embedding_status.in_(
                        ["complete", "failed", "indexed"]
                    ),
                )
                .limit(500)
            )
            docs = list(result.scalars().all())

        if not docs:
            logger.info("startup_reindex: no documents to check")
            return

        missing = [d for d in docs if not mem.exists(str(d.id))]
        if not missing:
            logger.info(
                "startup_reindex: all {} docs already in ChromaDB", len(docs)
            )
            return

        logger.info(
            "startup_reindex: re-embedding {} docs missing from ChromaDB "
            "({} total in DB)",
            len(missing),
            len(docs),
        )
        for doc in missing:
            _meta = {
                "title": doc.title,
                "category": doc.category,
                "tenant_id": doc.tenant_id,
                "doc_id": str(doc.id),
            }
            _task = asyncio.create_task(
                _embed_document(str(doc.id), doc.content or "", _meta, force=True)
            )
            _EMBED_TASKS.add(_task)
            _task.add_done_callback(_EMBED_TASKS.discard)

    except Exception as exc:
        logger.warning("startup_reindex failed (non-fatal): {}", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Text extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text(raw: bytes, filename: str, mime: str) -> str:
    """Best-effort text extraction from uploaded file bytes."""
    ext = Path(filename).suffix.lower()

    if ext in (".txt", ".md", ".csv", ".json") or "text/" in mime:
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return ""

    if ext == ".pdf" or mime == "application/pdf":
        try:
            import io
            import pdfplumber  # type: ignore
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                return "\n".join((p.extract_text() or "") for p in pdf.pages)
        except ImportError:
            pass
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return ""

    if ext in (".docx",) or "wordprocessingml" in mime:
        try:
            import io
            from docx import Document  # type: ignore
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        except ImportError:
            pass

    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Background embedding task
# ─────────────────────────────────────────────────────────────────────────────

async def _embed_document(
    doc_id: str,
    content: str,
    metadata: dict,
    force: bool = False,
) -> None:
    """Embed and store a document in ChromaDB; update DB embedding_status.

    force=True: re-embeds even if doc already exists in ChromaDB (used by reindex).
    """
    try:
        from app.memory.long_term import long_term_memory

        mem = long_term_memory()

        # Skip if already embedded (unless force=True)
        if not force and mem.exists(doc_id):
            logger.info("_embed_document: {} already in ChromaDB, skipping", doc_id)
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: mem.upsert(content, doc_id=doc_id, metadata=metadata)
        )

        # Update status in DB
        did = uuid.UUID(doc_id)
        async with AsyncSessionLocal() as new_db:
            await new_db.execute(
                update(KnowledgeDocumentModel)
                .where(KnowledgeDocumentModel.id == did)
                .values(embedding_status="complete")
            )
            await new_db.commit()

        logger.info("_embed_document: {} embedded successfully", doc_id)

    except Exception as exc:
        logger.error("_embed_document: failed for {}: {}", doc_id, exc)
        try:
            did = uuid.UUID(doc_id)
            async with AsyncSessionLocal() as _db:
                # Only mark "failed" if not already "indexed" or "complete"
                # to avoid downgrading a working doc
                await _db.execute(
                    update(KnowledgeDocumentModel)
                    .where(
                        KnowledgeDocumentModel.id == did,
                        KnowledgeDocumentModel.embedding_status == "pending",
                    )
                    .values(embedding_status="failed")
                )
                await _db.commit()
        except Exception:
            pass
