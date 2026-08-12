"""Ingest pipeline: parse → dedupe → chunk → FTS + vectors."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.audit import audit_log, now_iso
from app.bm25 import BM25Engine
from app.chunker import ChunkingEngine
from app.config import get_settings
from app.dedupe import DedupeEngine, canonicalize_content, canonicalize_timestamp, compute_fingerprint
from app.embedder import ChromaVectorDB, EmbeddingEngine
from app.metrics import ingest_total, vectors_indexed_total
from app.parsers import iter_messages

logger = logging.getLogger(__name__)


class ChatGPTIngestPipeline:
    def __init__(
        self,
        conn,
        embedder: EmbeddingEngine | None = None,
        vector_db: ChromaVectorDB | None = None,
        force_ingest: bool | None = None,
        db_path: str | None = None,
        chroma_path: str | None = None,
    ):
        settings = get_settings()
        self.conn = conn
        self.dedupe = DedupeEngine(conn)
        self.chunker = ChunkingEngine(
            chunk_size_tokens=settings.chunk_size_tokens,
            overlap_pct=settings.chunk_overlap_pct,
            fallback_chunk_chars=settings.fallback_chunk_chars,
        )
        self.bm25 = BM25Engine(conn)
        self.embedder = embedder or EmbeddingEngine(
            provider=settings.embedding_provider,
            model_name=settings.embedding_model,
            batch_size=settings.embedding_batch_size,
            quantize_level=settings.quantize_level,
        )
        persist = chroma_path or settings.chroma_persist_dir
        self.vector_db = vector_db or ChromaVectorDB(persist_dir=persist, collection_name=settings.chroma_collection)
        self.force_ingest = settings.force_ingest if force_ingest is None else force_ingest

    def ingest(self, payload: Any, export_filename: str, source_platform: str = "chatgpt") -> dict[str, Any]:
        messages = list(iter_messages(payload, source_platform))
        total = len(messages)
        processed = 0
        skipped = 0
        failed: list[dict[str, str]] = []
        all_chunks: list[dict[str, Any]] = []
        last_ts = now_iso()

        for offset, raw in enumerate(messages):
            try:
                content = raw["content"]
                timestamp = canonicalize_timestamp(raw["timestamp"])
                session_id = raw.get("session_id") or "sess_unknown"
                mid, is_dup = self.dedupe.dedupe(
                    content=content,
                    timestamp=timestamp,
                    session_id=session_id,
                    source_platform=source_platform,
                    platform_message_id=raw.get("platform_message_id"),
                    export_file=export_filename,
                    force_ingest=self.force_ingest,
                )
                if is_dup:
                    skipped += 1
                    continue
                fp = compute_fingerprint(canonicalize_content(content), timestamp, source_platform)
                ingested_at = now_iso()
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO messages
                    (message_id, session_id, source_platform, platform_message_id, timestamp,
                     role, content, tokens, export_file, sha256, ingested_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        mid,
                        session_id,
                        source_platform,
                        raw.get("platform_message_id"),
                        timestamp,
                        raw.get("role", "other"),
                        content,
                        None,
                        export_filename,
                        fp,
                        ingested_at,
                    ),
                )
                chunks = self.chunker.chunk_message(
                    content=content,
                    message_id=mid,
                    role=raw.get("role", "other"),
                    timestamp=timestamp,
                    source_platform=source_platform,
                    export_file=export_filename,
                )
                for ch in chunks:
                    cid = f"{mid}:{ch['chunk_index']}"
                    self.conn.execute(
                        """
                        INSERT OR REPLACE INTO chunks
                        (id, message_id, chunk_index, chunk_count, content, chunk_tokens,
                         chunk_sha256, role, timestamp, source_platform, export_file)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cid,
                            ch["message_id"],
                            ch["chunk_index"],
                            ch["chunk_count"],
                            ch["content"],
                            ch["chunk_tokens"],
                            ch["chunk_sha256"],
                            ch["role"],
                            ch["timestamp"],
                            ch["source_platform"],
                            ch["export_file"],
                        ),
                    )
                all_chunks.extend(chunks)
                processed += 1
                last_ts = timestamp
                ingest_total.labels(source_platform=source_platform, status="ok").inc()
            except Exception as exc:
                logger.exception("Failed message at offset %s", offset)
                failed.append({"message_id": str(raw.get("platform_message_id")), "error": str(exc)})
                ingest_total.labels(source_platform=source_platform, status="failed").inc()

        self.conn.commit()
        if all_chunks:
            self.bm25.index_chunks(all_chunks)
            texts = [f"[{c['role'].upper()}] {c['content']}" for c in all_chunks]
            embeddings, _ = self.embedder.embed_batch(texts)
            ids = [f"{c['message_id']}:{c['chunk_index']}" for c in all_chunks]
            metas = [
                {
                    "message_id": c["message_id"],
                    "chunk_index": int(c["chunk_index"]),
                    "role": c["role"],
                    "timestamp": c["timestamp"],
                    "source_platform": c["source_platform"],
                    "export_file": c["export_file"],
                }
                for c in all_chunks
            ]
            self.vector_db.add_embeddings(ids, embeddings, metas, [c["content"] for c in all_chunks])
            vectors_indexed_total.inc(len(all_chunks))

        self.dedupe.save_checkpoint(export_filename, source_platform, total, last_ts, processed)
        result = {
            "status": "completed",
            "total_messages": processed,
            "total_chunks": len(all_chunks),
            "messages_skipped_dedupe": skipped,
            "failed_messages": failed,
            "total_messages_in_file": total,
        }
        audit_log({"event": "ingest_complete", **result, "export_filename": export_filename})
        return result


# Shared singletons so ingest and search hit the same vector index.
_shared_embedder: EmbeddingEngine | None = None
_shared_vectors: ChromaVectorDB | None = None


def get_shared_engines() -> tuple[EmbeddingEngine, ChromaVectorDB]:
    global _shared_embedder, _shared_vectors
    if _shared_embedder is None:
        settings = get_settings()
        _shared_embedder = EmbeddingEngine(
            provider=settings.embedding_provider,
            model_name=settings.embedding_model,
            batch_size=settings.embedding_batch_size,
            quantize_level=settings.quantize_level,
        )
        _shared_vectors = ChromaVectorDB(
            persist_dir=settings.chroma_persist_dir,
            collection_name=settings.chroma_collection,
        )
    return _shared_embedder, _shared_vectors  # type: ignore[return-value]


def run_ingest_job(conn, ingest_id: str, file_content: bytes, filename: str, source_platform: str) -> None:
    settings = get_settings()
    try:
        conn.execute(
            "UPDATE ingest_jobs SET status = ?, progress_pct = ? WHERE id = ?",
            ("processing", 5, ingest_id),
        )
        conn.commit()
        payload = json.loads(file_content.decode("utf-8"))
        emb, vec = get_shared_engines()
        pipeline = ChatGPTIngestPipeline(conn, embedder=emb, vector_db=vec)
        result = pipeline.ingest(payload, filename, source_platform)
        conn.execute(
            "UPDATE ingest_jobs SET status = ?, progress_pct = ?, checkpoint = ? WHERE id = ?",
            ("completed", 100, json.dumps(result), ingest_id),
        )
        conn.commit()
    except Exception as exc:
        dest = Path(settings.failed_exports_dir)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{ingest_id}_{filename}").write_bytes(file_content)
        conn.execute(
            "UPDATE ingest_jobs SET status = ?, error = ? WHERE id = ?",
            ("failed", str(exc), ingest_id),
        )
        conn.commit()
        audit_log({"event": "ingest_failed", "ingest_id": ingest_id, "error": str(exc)})
