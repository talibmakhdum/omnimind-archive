# OmniMind Archive

Privacy-first, local-by-default semantic search for chat export archives.

## Quick start (local)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
# leave API_KEY empty and AUTH_REQUIRED=false for an open local UI
python backend/scripts/init_db.py

cd backend && PYTHONPATH=. uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
cd ui && streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

Upload `samples/chatgpt_sample.json` (both consent boxes) then search `machine learning`.

## Production deployment checklist

1. Set a strong `API_KEY` and `AUTH_REQUIRED=true`.
2. Set `ALLOWED_ORIGINS` to your UI origin only (no `*`).
3. Set `ALLOW_INMEMORY_VECTORS=false` after installing `backend/requirements-ml.txt`.
4. Persist `DATA_DIR` (SQLite) and `CHROMA_PERSIST_DIR` on named volumes.
5. Run Redis + API + RQ worker (`QUEUE_BACKEND=rq`, `REDIS_URL=redis://redis:6379/0`).
6. Optionally set `SENTRY_DSN`.
7. Back up SQLite + Chroma on a schedule (see below).
8. Expose `/health`, `/ready`, `/live`, `/metrics`; keep `/admin/*` behind the API key.

## Environment variables

| Variable | Purpose |
|---|---|
| `API_KEY` | Bearer token for `/ingest`, `/query`, `/admin/*` |
| `AUTH_REQUIRED` | Force auth even if `API_KEY` is empty |
| `ALLOWED_ORIGINS` | CORS allow-list |
| `DATA_DIR` | SQLite directory (`archive.db`) |
| `CHROMA_PERSIST_DIR` | Durable Chroma path |
| `ALLOW_INMEMORY_VECTORS` | Dev-only fallback when Chroma is missing |
| `REDIS_URL` | Redis for RQ + rate limits |
| `QUEUE_BACKEND` | `memory` (dev/CI) or `rq` |
| `RATE_LIMIT_*` | Ingest / search / query windows |
| `SENTRY_DSN` | Optional error reporting |

## Docker Compose (Redis + worker + volumes)

```bash
export API_KEY=changeme
docker compose up --build
```

This repo uses **RQ + Redis** (not Celery). Start the worker with `python -m app.worker` or the `worker` Compose service.

## Backups

```bash
sqlite3 "$DATA_DIR/archive.db" ".backup backup-$(date +%F).db"
tar -czf chroma-$(date +%F).tgz -C "$CHROMA_PERSIST_DIR" .
```

Restore by copying the SQLite backup over `archive.db` and extracting the Chroma tarball into `CHROMA_PERSIST_DIR`.

## Tests

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

CI definition: `docs/github-actions-ci.yml` (copy to `.github/workflows/ci.yml` if your token can write workflows).

### Manual Chroma test

```bash
pip install -r backend/requirements-ml.txt
ALLOW_INMEMORY_VECTORS=false python -c "from app.embedder import ChromaVectorDB; print(ChromaVectorDB().backend)"
```

See `CHANGELOG.md` for breaking changes and rollback.
