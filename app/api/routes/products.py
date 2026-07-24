"""Products / Services catalog API.

Beginner-friendly alternative to uploading knowledge-base documents: an
admin fills in a simple form (name, description, category, price, SKU) and
the product is immediately:
1. Saved as a structured row in the `products` table (for the catalog UI).
2. Converted into a short text blob and pushed through the same knowledge
   base pipeline used by document uploads (`app.api.routes.knowledge`), so
   voice/chat agents can answer questions about it right away.

Editing a product re-syncs its KB entry; deleting a product removes both.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import update

from app.core.logging import logger
from app.db.crud import (
    create_product,
    list_products,
    get_product,
    update_product,
    delete_product,
    create_knowledge_document,
    get_knowledge_document,
    delete_knowledge_document,
)
from app.db.models import KnowledgeDocumentModel
from app.db.session import get_db
from app.models.schemas import Principal
from app.security.auth import get_principal

router = APIRouter(prefix="/products", tags=["products"])

# Reuse the same in-flight background-task registry pattern as knowledge.py
_EMBED_TASKS: set = set()


class ProductIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    category: str | None = None
    price: str | None = None
    sku: str | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    price: str | None = None
    sku: str | None = None
    is_active: bool | None = None


def _product_out(p) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "category": p.category,
        "price": p.price,
        "sku": p.sku,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _build_kb_text(name: str, description: str, category: str | None, price: str | None, sku: str | None) -> str:
    lines = [f"Product/Service: {name}"]
    if category:
        lines.append(f"Category: {category}")
    if description:
        lines.append(description)
    if price:
        lines.append(f"Price: {price}")
    if sku:
        lines.append(f"SKU: {sku}")
    return "\n".join(lines)


async def _sync_kb_entry(
    db,
    *,
    tenant_id: str,
    product_id: uuid.UUID,
    existing_doc_id: uuid.UUID | None,
    name: str,
    description: str,
    category: str | None,
    price: str | None,
    sku: str | None,
    uploaded_by: str | None,
) -> uuid.UUID:
    """Create or refresh the KnowledgeDocumentModel backing a product, then
    (re)embed it into the vector store. Returns the KB document id."""
    content = _build_kb_text(name, description, category, price, sku)

    if existing_doc_id is not None:
        doc = await get_knowledge_document(db, existing_doc_id)
    else:
        doc = None

    if doc is None:
        doc = await create_knowledge_document(
            db,
            tenant_id=tenant_id,
            title=name,
            category="Products",
            content=content,
            uploaded_by=uploaded_by,
            metadata={"product_id": str(product_id)},
        )
    else:
        await db.execute(
            update(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == doc.id)
            .values(title=name, content=content, embedding_status="indexed")
        )
        doc.title = name
        doc.content = content

    await db.flush()

    _meta = {
        "title": name,
        "category": "Products",
        "tenant_id": tenant_id,
        "doc_id": str(doc.id),
        "product_id": str(product_id),
    }
    from app.api.routes.knowledge import _embed_document
    _task = asyncio.create_task(_embed_document(str(doc.id), content, _meta, force=True))
    _EMBED_TASKS.add(_task)
    _task.add_done_callback(_EMBED_TASKS.discard)

    return doc.id


@router.get("")
@router.get("/")
async def list_products_endpoint(
    category: str | None = None,
    active_only: bool = False,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict[str, Any]:
    products = await list_products(
        db,
        tenant_id=principal.tenant_id or "default",
        category=category,
        active_only=active_only,
    )
    return {"products": [_product_out(p) for p in products], "total": len(products)}


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_product_endpoint(
    payload: ProductIn,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict[str, Any]:
    tenant_id = principal.tenant_id or "default"
    product = await create_product(
        db,
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        price=payload.price,
        sku=payload.sku,
        is_active=payload.is_active,
        created_by=principal.user_id,
    )

    doc_id = await _sync_kb_entry(
        db,
        tenant_id=tenant_id,
        product_id=product.id,
        existing_doc_id=None,
        name=product.name,
        description=product.description,
        category=product.category,
        price=product.price,
        sku=product.sku,
        uploaded_by=principal.user_id,
    )
    product.knowledge_document_id = doc_id
    await db.flush()
    await db.refresh(product)
    await db.commit()

    logger.info("Product created: {} '{}' (tenant={})", product.id, product.name, tenant_id)
    return _product_out(product)


@router.put("/{product_id}")
async def update_product_endpoint(
    product_id: str,
    payload: ProductUpdate,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> dict[str, Any]:
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID")

    existing = await get_product(db, pid)
    if existing is None or existing.tenant_id != (principal.tenant_id or "default"):
        raise HTTPException(status_code=404, detail="Product not found")

    product = await update_product(
        db,
        pid,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        price=payload.price,
        sku=payload.sku,
        is_active=payload.is_active,
    )

    doc_id = await _sync_kb_entry(
        db,
        tenant_id=product.tenant_id,
        product_id=product.id,
        existing_doc_id=product.knowledge_document_id,
        name=product.name,
        description=product.description,
        category=product.category,
        price=product.price,
        sku=product.sku,
        uploaded_by=principal.user_id,
    )
    if product.knowledge_document_id != doc_id:
        product.knowledge_document_id = doc_id
        await db.flush()
        await db.refresh(product)
    await db.commit()

    logger.info("Product updated: {} '{}'", product.id, product.name)
    return _product_out(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_endpoint(
    product_id: str,
    principal: Principal = Depends(get_principal),
    db=Depends(get_db),
) -> None:
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID")

    existing = await get_product(db, pid)
    if existing is None or existing.tenant_id != (principal.tenant_id or "default"):
        raise HTTPException(status_code=404, detail="Product not found")

    doc_id = existing.knowledge_document_id
    await delete_product(db, pid)

    if doc_id is not None:
        try:
            from app.memory.long_term import long_term_memory
            long_term_memory().delete(str(doc_id))
        except Exception:
            pass
        try:
            await delete_knowledge_document(db, doc_id)
        except Exception:
            pass

    await db.commit()
    logger.info("Product deleted: {}", pid)
