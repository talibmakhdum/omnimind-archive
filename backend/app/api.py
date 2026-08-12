"""FastAPI application."""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.audit import audit_log, now_iso
from app.config import ensure_dirs, get_settings
from app.db import connect, init_db
from app.ingest import get_shared_engines, run_ingest_job
from app.schema import RAGQuery
from app.search import SearchService

settings = get_settings()
ensure_dirs(settings)
conn = init_db(connect(settings.db_path))
_emb, _vec = get_shared_engines()
search_service = SearchService(conn, embedder=_emb, vector_db=_vec)

app = FastAPI(title="OmniMind Archive", version="1.0.0")

if settings.cors_enabled:
    origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    origins += ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

_rate: dict[str, list[float]] = defaultdict(list)
_rate_lock = threading.Lock()


def check_rate(key: str, limit: int, window: float) -> None:
    now = time.time()
    with _rate_lock:
        bucket = [t for t in _rate[key] if now - t < window]
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        bucket.append(now)
        _rate[key] = bucket


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": now_iso(),
        "vector_db_status": "ok",
        "database_status": "ok",
        "local_only": settings.local_only,
    }


@app.post("/ingest")
async def ingest(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_platform: str = Form("chatgpt"),
    tos_url: str = Form("https://openai.com/terms/"),
    tos_version: str = Form("2024-01-15"),
    consent_given: bool = Form(False),
):
    check_rate("ingest", settings.rate_limit_ingest_per_hour, 3600)
    if not consent_given:
        raise HTTPException(status_code=403, detail="User consent required")
    if source_platform not in {"chatgpt", "gemini", "deepseek", "arena"}:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    ingest_id = str(uuid.uuid4())
    filename = file.filename or "export.json"
    sha = hashlib.sha256(content).hexdigest()
    conn.execute(
        """
        INSERT INTO consent_records
        (id, user_id, timestamp, source_platform, tos_url, tos_version, consent_given,
         consent_details, export_filename, export_sha256, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            "local_user",
            now_iso(),
            source_platform,
            tos_url,
            tos_version,
            1,
            json.dumps({"process_locally": True, "store_on_device": True}),
            filename,
            sha,
            "XXX",
            (request.headers.get("user-agent") or "unknown").split("/")[0],
        ),
    )
    conn.execute(
        "INSERT INTO ingest_jobs (id, status, progress_pct, eta_seconds, created_at) VALUES (?, ?, ?, ?, ?)",
        (ingest_id, "queued", 0, 60, now_iso()),
    )
    conn.commit()
    audit_log(
        {
            "event": "ingest_start",
            "ingest_id": ingest_id,
            "export_filename": filename,
            "export_size_bytes": len(content),
        }
    )
    background_tasks.add_task(run_ingest_job, conn, ingest_id, content, filename, source_platform)
    return {
        "ingest_id": ingest_id,
        "status": "queued",
        "filename": filename,
        "estimated_wait_seconds": 60,
    }


@app.get("/ingest/{ingest_id}/status")
async def ingest_status(ingest_id: str):
    row = conn.execute(
        "SELECT status, progress_pct, eta_seconds, checkpoint, error FROM ingest_jobs WHERE id = ?",
        (ingest_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Ingest not found")
    checkpoint = json.loads(row[3]) if row[3] else None
    return {
        "ingest_id": ingest_id,
        "status": row[0],
        "progress_pct": row[1],
        "eta_seconds": row[2],
        "checkpoint": checkpoint,
        "error": row[4],
    }


@app.get("/search")
async def search(q: str, k: int = 10, redact_level: str = "min"):
    check_rate("search", settings.rate_limit_search_per_minute, 60)
    if not q:
        raise HTTPException(status_code=400, detail="Query required")
    k = max(1, min(k, 50))
    if redact_level not in {"none", "min", "max"}:
        redact_level = "min"
    return search_service.hybrid(q, k, redact_level)


@app.get("/search/{search_id}/results")
async def search_results(search_id: str, k: int = 10):
    row = conn.execute(
        "SELECT status, bm25_results, vector_results FROM search_jobs WHERE id = ?",
        (search_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Search not found")
    if row[0] == "pending":
        return {"search_id": search_id, "status": "pending", "results": []}
    from app.retriever import RRFRetriever

    bm25_results = json.loads(row[1] or "[]")
    vector_results = json.loads(row[2] or "[]")
    fused = RRFRetriever(
        alpha_vector=settings.alpha_vector,
        alpha_bm25=settings.alpha_bm25,
        rrf_k=settings.rrf_k,
        final_top_k=k,
    ).fuse_results(bm25_results, vector_results)
    return {"search_id": search_id, "status": "completed", "results": fused[:k], "vector_status": "completed"}


@app.post("/query")
async def query_rag(body: RAGQuery):
    check_rate("query", settings.rate_limit_query_per_minute, 60)
    return search_service.rag(body.q, body.redact_level)
