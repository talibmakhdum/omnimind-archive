"""FastAPI application."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.audit import audit_log, now_iso
from app.auth import list_stored_api_keys, require_api_key, revoke_api_key, store_api_key
from app.config import ensure_dirs, get_settings
from app.db import db_health, get_connection, init_db
from app.ingest import get_shared_engines
from app.jobs import enqueue_ingest, queue_length
from app.logging_setup import configure_logging, init_sentry
from app.metrics import (
    CONTENT_TYPE_LATEST,
    QUEUE_LENGTH,
    metrics_response_body,
    observe_request,
    set_vector_health,
    vectors_in_db,
)
from app.rate_limit import RateLimitMiddleware
from app.schema import RAGQuery
from app.search import SearchService
from app.validation import UploadValidationError, validate_upload

logger = logging.getLogger(__name__)

_ID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _normalize_path(path: str) -> str:
    return _ID_RE.sub("{id}", path)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging()
    init_sentry()
    ensure_dirs(settings)
    init_db()
    _emb, vec = get_shared_engines()
    status = vec.health() if hasattr(vec, "health") else "ok"
    if getattr(vec, "backend", "") == "memory" and status == "ok":
        status = "memory"
    set_vector_health(status)
    if hasattr(vec, "count"):
        vectors_in_db.set(vec.count())
    QUEUE_LENGTH.set(queue_length())
    yield


settings = get_settings()
app = FastAPI(
    title="OmniMind Archive",
    version="1.2.0",
    description="Privacy-first local semantic search for chat export archives.",
    lifespan=lifespan,
)

if settings.cors_enabled:
    origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    path = _normalize_path(request.url.path)
    observe_request(path, request.method, response.status_code, time.perf_counter() - started)
    return response


def _search_service(conn) -> SearchService:
    emb, vec = get_shared_engines()
    return SearchService(conn, embedder=emb, vector_db=vec)


@app.get("/health", tags=["ops"])
async def health():
    db_ok = db_health()
    try:
        _, vec = get_shared_engines()
        vec_status = vec.health() if hasattr(vec, "health") else "ok"
        if getattr(vec, "backend", "") == "memory" and vec_status == "ok":
            vec_status = "memory"
        set_vector_health(vec_status)
        if hasattr(vec, "count"):
            vectors_in_db.set(vec.count())
    except Exception:
        vec_status = "error"
        set_vector_health("error")
    QUEUE_LENGTH.set(queue_length())
    status = "ok" if db_ok and vec_status != "error" else "degraded"
    return {
        "status": status,
        "timestamp": now_iso(),
        "vector_db_status": vec_status,
        "database_status": "ok" if db_ok else "error",
        "queue_length": queue_length(),
        "local_only": settings.local_only,
    }


@app.get("/live", tags=["ops"])
async def liveness():
    return {"status": "alive"}


@app.get("/ready", tags=["ops"])
async def readiness():
    if not db_health():
        raise HTTPException(status_code=503, detail="database not ready")
    return {"status": "ready"}


@app.get("/metrics", tags=["ops"])
async def metrics():
    return Response(content=metrics_response_body(), media_type=CONTENT_TYPE_LATEST)


@app.get("/admin/stats", dependencies=[Depends(require_api_key)], tags=["admin"])
async def admin_stats():
    with get_connection() as conn:
        messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        jobs = conn.execute("SELECT COUNT(*) FROM ingest_jobs").fetchone()[0]
    _, vec = get_shared_engines()
    return {
        "messages": messages,
        "ingest_jobs": jobs,
        "vector_backend": getattr(vec, "backend", "unknown"),
        "queue_length": queue_length(),
    }


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


@app.post("/admin/api-keys", dependencies=[Depends(require_api_key)], tags=["admin"])
async def create_api_key(body: ApiKeyCreate):
    with get_connection() as conn:
        created = store_api_key(conn, body.name)
    # Return plaintext once; only the bcrypt hash is stored.
    return {"id": created["id"], "name": created["name"], "api_key": created["api_key"]}


@app.get("/admin/api-keys", dependencies=[Depends(require_api_key)], tags=["admin"])
async def list_api_keys():
    with get_connection() as conn:
        return {"keys": list_stored_api_keys(conn)}


@app.delete("/admin/api-keys/{key_id}", dependencies=[Depends(require_api_key)], tags=["admin"])
async def delete_api_key(key_id: str):
    with get_connection() as conn:
        ok = revoke_api_key(conn, key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"id": key_id, "revoked": True}


@app.post("/ingest", dependencies=[Depends(require_api_key)], tags=["ingest"])
async def ingest(
    request: Request,
    file: UploadFile = File(...),
    source_platform: str = Form("chatgpt"),
    tos_url: str = Form("https://openai.com/terms/"),
    tos_version: str = Form("2024-01-15"),
    consent_given: bool = Form(False),
):
    if not consent_given:
        raise HTTPException(status_code=403, detail="User consent required")
    if source_platform not in {"chatgpt", "gemini", "deepseek", "arena"}:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    try:
        validate_upload(
            content,
            max_bytes=max_bytes,
            filename=file.filename,
            declared_mime=file.content_type,
            require_json_object=True,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    ingest_id = str(uuid.uuid4())
    filename = file.filename or "export.json"
    sha = hashlib.sha256(content).hexdigest()
    dest = Path(settings.upload_dir)
    dest.mkdir(parents=True, exist_ok=True)
    stored = dest / f"{ingest_id}.json"
    stored.write_bytes(content)

    with get_connection() as conn:
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

    audit_log(
        {
            "event": "ingest_start",
            "ingest_id": ingest_id,
            "export_filename": filename,
            "export_size_bytes": len(content),
        }
    )
    logger.info("enqueue ingest", extra={"ingest_id": ingest_id})
    enqueue_ingest(ingest_id, str(stored), filename, source_platform)
    QUEUE_LENGTH.set(queue_length())
    return {
        "ingest_id": ingest_id,
        "status": "queued",
        "filename": filename,
        "estimated_wait_seconds": 60,
    }


@app.get("/ingest/{ingest_id}/status", tags=["ingest"])
async def ingest_status(ingest_id: str):
    with get_connection() as conn:
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


@app.get("/search", tags=["search"])
async def search(q: str, k: int = 10, redact_level: str = "min"):
    if not q:
        raise HTTPException(status_code=400, detail="Query required")
    k = max(1, min(k, 50))
    if redact_level not in {"none", "min", "max"}:
        redact_level = "min"
    with get_connection() as conn:
        result = _search_service(conn).hybrid(q, k, redact_level)
    logger.info("search", extra={"search_id": result.get("search_id")})
    return result


@app.get("/search/{search_id}/results", tags=["search"])
async def search_results(search_id: str, k: int = 10):
    with get_connection() as conn:
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
    return {
        "search_id": search_id,
        "status": "completed",
        "results": fused[:k],
        "vector_status": "completed",
    }


@app.post("/query", dependencies=[Depends(require_api_key)], tags=["search"])
async def query_rag(body: RAGQuery):
    with get_connection() as conn:
        return _search_service(conn).rag(body.q, body.redact_level)
