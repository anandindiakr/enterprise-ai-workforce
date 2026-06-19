"""Long-term vector memory using ChromaDB.

Stores embedded conversation summaries, knowledge documents and per-agent
memories for retrieval-augmented generation.

Embedding strategy (in priority order)
---------------------------------------
1. OpenAI ``text-embedding-3-small`` — reliable, fast, no local model needed.
   Requires ``OPENAI_API_KEY`` to be set.
2. ChromaDB's ``DefaultEmbeddingFunction`` (all-MiniLM-L6-v2 via onnxruntime)
   — only used if OpenAI key is absent.  Requires ``chromadb[default-embedding-function]``
   which installs sentence-transformers; may fail on low-memory VPS.

Connection strategy
--------------------
1. Try the remote Chroma server (``HttpClient``) — used in Docker/production
   where a dedicated ``chroma`` service is running.
2. If that fails, fall back to an embedded ``PersistentClient`` that stores
   vectors on local disk.  This guarantees the KB works without extra infra.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import chromadb

from app.core.config import settings
from app.core.logging import logger


# ---------------------------------------------------------------------------
# OpenAI embedding function (primary — no local model required)
# ---------------------------------------------------------------------------

class _OpenAIEmbeddingFunction:
    """Thin wrapper that satisfies ChromaDB's EmbeddingFunction protocol.

    ChromaDB >= 0.6 requires embedding functions to expose a ``name()`` method
    so it can validate the function matches what was used when the collection
    was first created.
    """

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self._api_key = api_key
        self._model = model

    def name(self) -> str:
        """Required by ChromaDB >= 0.6 to identify the embedding function type."""
        return f"openai_{self._model.replace('-', '_')}"

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        from openai import OpenAI  # imported lazily so startup is fast

        client = OpenAI(api_key=self._api_key)
        # Batch in chunks of 100 to stay within OpenAI's per-request limit
        results: list[list[float]] = []
        for i in range(0, len(input), 100):
            batch = input[i : i + 100]
            resp = client.embeddings.create(input=batch, model=self._model)
            results.extend([d.embedding for d in resp.data])
        return results


def _make_embedding_function():
    """Return best available embedding function."""
    api_key = getattr(settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY")
    if api_key:
        logger.info("LongTermMemory: using OpenAI text-embedding-3-small")
        return _OpenAIEmbeddingFunction(api_key=api_key)

    # Fallback: chromadb default (sentence-transformers / onnxruntime)
    try:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction  # type: ignore
        logger.warning(
            "LongTermMemory: OPENAI_API_KEY not set — falling back to "
            "DefaultEmbeddingFunction (requires onnxruntime/sentence-transformers)"
        )
        return DefaultEmbeddingFunction()
    except Exception as exc:
        logger.error("LongTermMemory: no embedding function available: {}", exc)
        return None


# ---------------------------------------------------------------------------
# LongTermMemory
# ---------------------------------------------------------------------------

class LongTermMemory:
    """Wrapper over a Chroma client (remote or embedded) with sensible defaults."""

    def __init__(self, collection: str | None = None) -> None:
        self._collection_name = collection or settings.chroma_collection
        self._client: chromadb.api.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None
        self._ef = _make_embedding_function()

    def connect(self) -> None:
        if self._client is not None:
            return

        client = None
        # 1) Remote Chroma server (Docker/prod)
        try:
            client = chromadb.HttpClient(
                host=settings.chroma_host, port=settings.chroma_port
            )
            client.heartbeat()
            logger.info(
                "LongTermMemory: remote Chroma at {}:{}",
                settings.chroma_host,
                settings.chroma_port,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "LongTermMemory: remote Chroma unavailable ({}); "
                "falling back to embedded PersistentClient at {}",
                exc,
                settings.chroma_persist_dir,
            )
            client = None

        # 2) Embedded persistent client (local dev / no server)
        if client is None:
            os.makedirs(settings.chroma_persist_dir, exist_ok=True)
            client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            logger.info(
                "LongTermMemory: embedded Chroma at {}",
                settings.chroma_persist_dir,
            )

        self._client = client
        self._collection = self._get_or_create_collection()
        logger.info("LongTermMemory ready (collection={})", self._collection_name)

    def _get_or_create_collection(self) -> chromadb.Collection:
        """Create the collection, handling dimension-mismatch on re-creation."""
        assert self._client is not None
        kwargs: dict[str, Any] = {
            "name": self._collection_name,
            "metadata": {"hnsw:space": "cosine"},
        }
        if self._ef is not None:
            kwargs["embedding_function"] = self._ef
        try:
            return self._client.get_or_create_collection(**kwargs)
        except Exception as exc:
            # If collection exists with a different embedding dimension or
            # function name (ChromaDB >= 0.6 validates embedding function name)
            # delete and recreate it.
            msg = str(exc).lower()
            if (
                "dimension" in msg or "embedding" in msg or "mismatch" in msg
                or "conflict" in msg or "does not match" in msg
                or isinstance(exc, (ValueError, AttributeError))
            ):
                logger.warning(
                    "LongTermMemory: embedding dimension mismatch — "
                    "deleting and recreating collection '{}'. "
                    "All existing vectors will be re-indexed.",
                    self._collection_name,
                )
                try:
                    self._client.delete_collection(self._collection_name)
                except Exception:
                    pass
                return self._client.get_or_create_collection(**kwargs)
            raise

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self.connect()
        assert self._collection is not None
        return self._collection

    def _refresh_collection(self) -> chromadb.Collection:
        if self._client is None:
            self.connect()
        assert self._client is not None
        self._collection = self._get_or_create_collection()
        return self._collection

    @staticmethod
    def _is_missing_collection(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "does not exist" in msg or ("collection" in msg and "not found" in msg)

    def _retry(self, fn):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if not self._is_missing_collection(exc):
                raise
            logger.warning("LongTermMemory: collection missing ({}); recreating", exc)
            self._refresh_collection()
            return fn()

    # ---- Count -------------------------------------------------------

    def count(self) -> int:
        try:
            return self._retry(lambda: self.collection.count())
        except Exception:
            return 0

    # ---- Check existence -------------------------------------------------------

    def exists(self, doc_id: str) -> bool:
        """Return True if a document with this ID is already stored."""
        try:
            result = self._retry(
                lambda: self.collection.get(ids=[doc_id], include=[])
            )
            return bool((result.get("ids") or []))
        except Exception:
            return False

    # ---- Mutations ---------------------------------------------------

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

    def delete(self, doc_id: str) -> None:
        try:
            self._retry(lambda: self.collection.delete(ids=[doc_id]))
        except Exception as exc:
            logger.warning("LongTermMemory: delete failed for {}: {}", doc_id, exc)

    # ---- Retrieval ---------------------------------------------------

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            result = self._retry(
                lambda: self.collection.query(
                    query_texts=[query],
                    n_results=min(k, max(1, self.count())),
                    where=where,
                )
            )
        except Exception as exc:
            logger.warning("LongTermMemory: search failed: {}", exc)
            return []
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
