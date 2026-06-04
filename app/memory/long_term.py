"""Long-term vector memory using ChromaDB.

Stores embedded conversation summaries, knowledge documents and per-agent
memories for retrieval-augmented generation.

Connection strategy
--------------------
1. Try the remote Chroma server (``HttpClient``) — used in Docker/production
   where a dedicated ``chroma`` service is running.
2. If that fails (e.g. local dev with no Chroma server), fall back to an
   **embedded** ``PersistentClient`` that stores vectors on the local disk.
   This guarantees the knowledge base works out-of-the-box without any extra
   infrastructure.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import chromadb

from app.core.config import settings
from app.core.logging import logger


class LongTermMemory:
    """Wrapper over a Chroma client (remote or embedded) with sensible defaults."""

    def __init__(self, collection: str | None = None) -> None:
        self._collection_name = collection or settings.chroma_collection
        self._client: chromadb.api.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def connect(self) -> None:
        if self._client is not None:
            return

        client = None
        # 1) Remote Chroma server (Docker/prod)
        try:
            client = chromadb.HttpClient(
                host=settings.chroma_host, port=settings.chroma_port
            )
            # Force a real connection check — HttpClient is lazy.
            client.heartbeat()
            logger.info(
                "LongTermMemory using remote Chroma at {}:{}",
                settings.chroma_host,
                settings.chroma_port,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Remote Chroma unavailable ({}); falling back to embedded "
                "PersistentClient at {}",
                exc,
                settings.chroma_persist_dir,
            )
            client = None

        # 2) Embedded persistent client (local dev / no server)
        if client is None:
            import os

            os.makedirs(settings.chroma_persist_dir, exist_ok=True)
            client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            logger.info(
                "LongTermMemory using embedded Chroma at {}",
                settings.chroma_persist_dir,
            )

        self._client = client
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

    def _refresh_collection(self) -> chromadb.Collection:
        """Force-recreate the collection handle.

        Guards against the "Collection [uuid] does not exist" error that can
        occur when the Chroma server is reset/recreated while this process
        keeps a stale collection reference.
        """
        if self._client is None:
            self.connect()
        assert self._client is not None
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    @staticmethod
    def _is_missing_collection(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "does not exist" in msg or "collection" in msg and "not found" in msg

    def _retry(self, fn):
        """Run ``fn`` and, on a missing-collection error, recreate and retry once."""
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if not self._is_missing_collection(exc):
                raise
            logger.warning(
                "Chroma collection missing ({}); recreating and retrying", exc
            )
            self._refresh_collection()
            return fn()

    # ---- Mutations -----------------------------------------------------

    def upsert(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
        doc_id: str | None = None,
    ) -> str:
        doc_id = doc_id or str(uuid4())
        self._retry(
            lambda: self.collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata or {}],
            )
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
        self._retry(
            lambda: self.collection.upsert(
                ids=ids,
                documents=texts,
                metadatas=metadatas or [{} for _ in texts],
            )
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
        result = self._retry(
            lambda: self.collection.query(
                query_texts=[query],
                n_results=k,
                where=where,
            )
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
