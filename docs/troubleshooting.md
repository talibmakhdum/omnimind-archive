# Troubleshooting

## API will not start

- `DATA_DIR` not writable → `mkdir -p "$DATA_DIR"` or fix volume ownership (`uid 10001` in Docker).
- `ALLOW_INMEMORY_VECTORS=false` and Chroma missing → `pip install -r backend/requirements-ml.txt` or set the flag true for dev.
- Port 8000 in use → change `FASTAPI_PORT`.

## 401 on ingest / query / admin

Send `Authorization: Bearer <key>`. The Streamlit UI must have `API_KEY` set (it is forwarded on ingest and RAG). Keys created via `POST /admin/api-keys` are shown **once**.

## 400 Unsupported content type

Only JSON exports (and the documented image/PDF MIME set) pass sniffing. ChatGPT exports must start with `{` or `[`. Rename `.json` and re-export from the platform if the file is a zip.

## 413 File too large

Raise `MAX_UPLOAD_SIZE_MB` or split the export.

## 429 Rate limit exceeded

Wait for the window or raise `RATE_LIMIT_*`. Multi-process deployments need `REDIS_URL` so limiters share state.

## Search returns nothing after ingest

- Check `GET /ingest/{id}/status` for `failed` and the `error` field.
- Failed payloads land in `FAILED_EXPORTS_DIR`.
- Memory vector store is process-local: ingest and search must share one API process (`get_shared_engines`).
- Rebuild: re-ingest with `FORCE_INGEST=true`.

## Worker not draining

`QUEUE_BACKEND=rq` requires Redis and `python -m app.worker`. Locally use `QUEUE_BACKEND=memory` (jobs run in-process).

## Database locked

WAL + `busy_timeout=30000` should absorb brief contention. Avoid copying `archive.db` while writers run; use `scripts/backup_db.sh`.

## Alembic vs init_db mismatch

`python backend/scripts/init_db.py` tries Alembic then falls back to `SCHEMA`. Run `cd backend && PYTHONPATH=. alembic upgrade head` to stamp/apply revisions. See `docs/migrations.md`.

## Metrics empty

Hit any route once, then `GET /metrics`. `omnimind_requests_total` is recorded by middleware.

## Purge deleted too much / too little

Default is **dry-run**. `--execute` also requires `PURGE_ENABLED=true`. Compare `timestamp` / `ingested_at` to `--days`. Consent rows are kept.

## Restored backup looks empty

Confirm you restored **both** SQLite and the Chroma tarball into the same paths the process uses (`DATA_DIR`, `CHROMA_PERSIST_DIR`).
