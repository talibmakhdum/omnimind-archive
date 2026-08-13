"""Local embeddings with hash fallback for tests / offline CI."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

EMBED_DIM = 384


def hash_embedding(text: str, dim: int = EMBED_DIM) -> np.ndarray:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng_seed = int.from_bytes(digest[:8], "little") % (2**32)
    rng = np.random.default_rng(rng_seed)
    vec = rng.standard_normal(dim).astype(np.float32)
    norm = np.linalg.norm(vec) or 1.0
    return vec / norm


class EmbeddingEngine:
    def __init__(
        self,
        provider: str = "local",
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
        quantize_level: str = "none",
        device: str = "cpu",
        allow_fallback: bool = True,
    ):
        self.provider = provider
        self.model_name = model_name
        self.batch_size = batch_size
        self.quantize_level = quantize_level
        self.device = device
        self.allow_fallback = allow_fallback
        self.model = None
        self._initialize_model()

    def _initialize_model(self) -> None:
        if self.provider != "local":
            logger.warning("Only local embeddings are implemented in MVP; using local/fallback.")
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=".cache/embeddings",
            )
        except Exception as exc:
            if not self.allow_fallback:
                raise
            logger.warning("sentence-transformers unavailable (%s); using hash embeddings.", exc)
            self.model = None

    def embed_batch(self, texts: list[str]) -> tuple[np.ndarray, bool]:
        if self.model is not None:
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                convert_to_tensor=False,
                show_progress_bar=False,
            )
            embeddings = np.asarray(embeddings)
            if self.quantize_level == "float16":
                embeddings = embeddings.astype(np.float16)
            return embeddings, False
        arr = np.stack([hash_embedding(t) for t in texts])
        return arr, True

    def embed_single(self, text: str) -> tuple[np.ndarray, bool]:
        embeddings, used_fallback = self.embed_batch([text])
        return embeddings[0], used_fallback


class InMemoryVectorDB:
    """Lightweight vector store used when Chroma is unavailable."""

    def __init__(self) -> None:
        self.ids: list[str] = []
        self.embeddings: list[np.ndarray] = []
        self.metadatas: list[dict[str, Any]] = []
        self.documents: list[str] = []

    def add_embeddings(
        self,
        ids: list[str],
        embeddings: np.ndarray,
        metadatas: list[dict],
        documents: list[str],
    ) -> None:
        for i, _id in enumerate(ids):
            if _id in self.ids:
                idx = self.ids.index(_id)
                self.embeddings[idx] = embeddings[i]
                self.metadatas[idx] = metadatas[i]
                self.documents[idx] = documents[i]
            else:
                self.ids.append(_id)
                self.embeddings.append(np.asarray(embeddings[i]))
                self.metadatas.append(metadatas[i])
                self.documents.append(documents[i])

    def query(self, query_embedding: np.ndarray, top_k: int = 50) -> dict:
        if not self.embeddings:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mat = np.stack(self.embeddings)
        q = np.asarray(query_embedding, dtype=float)
        q = q / (np.linalg.norm(q) or 1.0)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        sims = (mat / norms) @ q
        order = np.argsort(-sims)[:top_k]
        return {
            "ids": [[self.ids[i] for i in order]],
            "documents": [[self.documents[i] for i in order]],
            "metadatas": [[self.metadatas[i] for i in order]],
            "distances": [[float(1.0 - sims[i]) for i in order]],
        }


class ChromaVectorDB:
    def __init__(
        self,
        persist_dir: str = ".chroma",
        collection_name: str = "omnimind_v1",
        allow_inmemory: bool | None = None,
    ):
        from app.config import get_settings

        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._backend: Any
        if allow_inmemory is None:
            allow_inmemory = get_settings().allow_inmemory_vectors
        try:
            import chromadb

            client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self._backend = "chroma"
        except Exception as exc:
            logger.warning("Chroma unavailable (%s); falling back to in-memory vectors.", exc)
            if not allow_inmemory:
                raise RuntimeError(
                    "Chroma unavailable and ALLOW_INMEMORY_VECTORS=false. "
                    "Install chromadb or set ALLOW_INMEMORY_VECTORS=true for development."
                ) from exc
            self.collection = InMemoryVectorDB()
            self._backend = "memory"

    def add_embeddings(
        self,
        ids: list[str],
        embeddings: np.ndarray,
        metadatas: list[dict],
        documents: list[str],
    ) -> None:
        if self._backend == "chroma":
            self.collection.add(
                ids=ids,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                documents=documents,
            )
        else:
            self.collection.add_embeddings(ids, embeddings, metadatas, documents)

    def query(self, query_embedding: np.ndarray, top_k: int = 50) -> dict:
        if self._backend == "chroma":
            return self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k,
                include=["metadatas", "documents", "distances"],
            )
        return self.collection.query(query_embedding, top_k)

    def health(self) -> str:
        return "ok" if self._backend in {"chroma", "memory"} else "degraded"

    @property
    def backend(self) -> str:
        return str(self._backend)
