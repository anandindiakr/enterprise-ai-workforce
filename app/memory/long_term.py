"""Long-term vector memory using ChromaDB.

Stores embedded conversation summaries, knowledge documents and per-agent
memories for retrieval-augmented generation.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import chromadb

from app.core.config import settings
from app.core.logging import logger


class LongTermMemory:
    """Wrapper over a Chroma HTTP client with sensible defaults."""

    def __init__(self, collection: str | None = None) -> None:
        self._collection_name = collection or settings.chroma_collection
        self._client: chromadb.api.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            self._client = chromadb.HttpClient(
                host=settings.chroma_host, port=settings.chroma_port
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Chroma HTTP client failed ({}); using in-memory fallback", exc)
            self._client = chromadb.EphemeralClient()

        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("LongTermMemory ready (collection={})", self._collection_name)

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self.connect()
        assert self._collection is not None
        return self._collection

    # ---- Mutations -----------------------------------------------------

    def upsert(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
        doc_id: str | None = None,
    ) -> str:
        doc_id = doc_id or str(uuid4())
        self.collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata or {}],
        )
        return doc_id

    def upsert_many(
        self,
        texts: list[str],
        *,
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        ids = ids or [str(uuid4()) for _ in texts]
        self.collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas or [{} for _ in texts],
        )
        return ids

    # ---- Retrieval -----------------------------------------------------

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        result = self.collection.query(
            query_texts=[query],
            n_results=k,
            where=where,
        )
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        return [
            {"id": i, "text": d, "metadata": m, "distance": dist}
            for i, d, m, dist in zip(ids, docs, metas, dists)
        ]


_long_term: LongTermMemory | None = None


def long_term_memory() -> LongTermMemory:
    global _long_term
    if _long_term is None:
        _long_term = LongTermMemory()
    return _long_term
