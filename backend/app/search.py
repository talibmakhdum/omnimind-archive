"""Hybrid search orchestration."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from app.audit import audit_log, now_iso
from app.bm25 import BM25Engine
from app.config import get_settings
from app.embedder import ChromaVectorDB, EmbeddingEngine
from app.metrics import search_latency_seconds, search_queries_total
from app.redactor import PIIRedactor
from app.retriever import RRFRetriever


def chroma_to_results(raw: dict[str, Any]) -> list[dict[str, Any]]:
    ids = (raw.get("ids") or [[]])[0]
    docs = (raw.get("documents") or [[]])[0]
    metas = (raw.get("metadatas") or [[]])[0]
    dists = (raw.get("distances") or [[]])[0]
    out: list[dict[str, Any]] = []
    for i, _id in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        dist = dists[i] if i < len(dists) else 1.0
        out.append(
            {
                "message_id": meta.get("message_id") or str(_id).split(":")[0],
                "chunk_index": meta.get("chunk_index", 0),
                "content": docs[i] if i < len(docs) else "",
                "role": meta.get("role", "other"),
                "timestamp": meta.get("timestamp", ""),
                "source_platform": meta.get("source_platform", "chatgpt"),
                "export_file": meta.get("export_file", ""),
                "vector_score": 1.0 / (1.0 + float(dist)),
            }
        )
    return out


def apply_redaction(results: list[dict[str, Any]], level: str) -> list[dict[str, Any]]:
    redactor = PIIRedactor(level)
    cleaned = []
    for r in results:
        text, fields = redactor.redact(r.get("content", ""))
        cleaned.append(
            {
                **r,
                "content": text,
                "pii_redacted": bool(fields),
                "pii_fields_redacted": fields,
            }
        )
    return cleaned


class SearchService:
    def __init__(self, conn, embedder: EmbeddingEngine | None = None, vector_db: ChromaVectorDB | None = None):
        settings = get_settings()
        self.conn = conn
        self.settings = settings
        self.bm25 = BM25Engine(conn)
        self.embedder = embedder or EmbeddingEngine()
        self.vector_db = vector_db or ChromaVectorDB(
            persist_dir=settings.chroma_persist_dir,
            collection_name=settings.chroma_collection,
        )
        self.rrf = RRFRetriever(
            alpha_vector=settings.alpha_vector,
            alpha_bm25=settings.alpha_bm25,
            rrf_k=settings.rrf_k,
            final_top_k=settings.final_top_k,
        )

    def bm25_search(self, q: str, k: int) -> tuple[list[dict[str, Any]], float]:
        t0 = time.perf_counter()
        hits = self.bm25.search(q, top_k=self.settings.bm25_top_k)
        ms = (time.perf_counter() - t0) * 1000
        search_queries_total.labels(method="bm25").inc()
        search_latency_seconds.labels(method="bm25").observe(ms / 1000)
        return hits[:k], ms

    def vector_search(self, q: str) -> tuple[list[dict[str, Any]], float]:
        t0 = time.perf_counter()
        emb, _ = self.embedder.embed_single(q)
        raw = self.vector_db.query(emb, top_k=self.settings.vector_top_k)
        hits = chroma_to_results(raw)
        ms = (time.perf_counter() - t0) * 1000
        search_queries_total.labels(method="vector").inc()
        search_latency_seconds.labels(method="vector").observe(ms / 1000)
        return hits, ms

    def hybrid(self, q: str, k: int, redact_level: str = "min") -> dict[str, Any]:
        search_id = str(uuid.uuid4())
        bm25_hits, bm25_ms = self.bm25_search(q, self.settings.bm25_top_k)
        vec_hits, vec_ms = self.vector_search(q)
        fused = self.rrf.fuse_results(bm25_hits, vec_hits)
        fused = apply_redaction(fused[:k], redact_level)
        self.conn.execute(
            """
            INSERT INTO search_jobs (id, status, query, bm25_results, vector_results, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                search_id,
                "completed",
                q,
                json.dumps(bm25_hits),
                json.dumps(vec_hits),
                now_iso(),
            ),
        )
        self.conn.commit()
        audit_log({"event": "search_query", "search_id": search_id, "query": q, "k": k})
        return {
            "search_id": search_id,
            "query": q,
            "results": fused,
            "bm25_hits": len(bm25_hits),
            "vector_hits": len(vec_hits),
            "vector_status": "completed",
            "bm25_latency_ms": bm25_ms,
            "vector_latency_ms": vec_ms,
            "total_latency_ms": bm25_ms + vec_ms,
        }

    def rag(self, q: str, redact_level: str = "min") -> dict[str, Any]:
        data = self.hybrid(q, self.settings.final_top_k, redact_level)
        sources = data["results"]
        if not sources:
            answer = "Insufficient evidence in archive."
            warning = answer
        else:
            snippets = []
            for i, s in enumerate(sources[:5], 1):
                snippets.append(
                    f"[{i}] ({s.get('source_platform')} {s.get('timestamp')} {s.get('export_file')})\n{s.get('content')}"
                )
            answer = (
                f"Based on {len(sources)} archived snippet(s) for “{q}”:\n\n"
                + "\n\n".join(snippets)
            )
            warning = None
        redactor = PIIRedactor(redact_level)
        answer, fields = redactor.redact(answer)
        audit_log({"event": "rag_query", "query": q, "result_snippets": len(sources)})
        return {
            "query": q,
            "answer": answer,
            "sources": sources,
            "synthesis_model": "template",
            "warning": warning,
            "pii_warning": f"Output contains {fields}" if fields else None,
        }
