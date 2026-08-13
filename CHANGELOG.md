# Changelog

## 1.2.0 — Production readiness

### Added
- Bcrypt API-key hashing (`hash_api_key` / `verify_api_key`); `api_keys` table via Alembic `0002`
- Upload validation (size, extension, magic-byte MIME sniff)
- Rate-limit middleware (Redis sliding window when configured)
- Retention purge (`scripts/purge_old_documents.py`) with dry-run tests and scheduled workflow example
- Prometheus request/latency/queue/vector-health metrics + Grafana dashboard and alert rules
- JSONL export/import (`omnimind.archive.export`)
- Python SDK skeleton (`sdk/omnimind`)
- GitHub Actions CI (3.10–3.12), Dependabot, issue/PR templates, `CONTRIBUTING.md`
- Ops docs: architecture diagram, OpenAPI notes, backup/restore, zero-downtime, threat model
- Test DB seeder and DB read/write + vector fallback tests

### Security
- API keys are never stored in plaintext
- Streamlit now forwards `Authorization` on ingest
- CORS remain allow-listed; uploads rejected on MIME/size mismatch

### Compatibility
- Public routes unchanged. Additive: `POST/GET/DELETE /admin/api-keys`, extra `/health` fields (`queue_length`)
- `0002` is backward compatible (`CREATE TABLE IF NOT EXISTS api_keys`)

### Rollback
```bash
cd backend && PYTHONPATH=. alembic downgrade 0001
```
Env `API_KEY` / `API_KEY_HASH` continue to authenticate after downgrade.

## 1.1.0 — Production hardening

### Breaking
- `/ingest` and `/query` (and `/admin/*`) require `Authorization: Bearer <API_KEY>` when `API_KEY` or `AUTH_REQUIRED` is set.
- CORS no longer allows `*`. Set `ALLOWED_ORIGINS` explicitly.
- Ingest is queued (`QUEUE_BACKEND=rq` + Redis in Compose). Local default `QUEUE_BACKEND=memory` still runs the job in-process.
- `run_ingest_job` no longer accepts a shared sqlite connection as the first argument; workers open their own connection.
- Chroma in-memory fallback is gated by `ALLOW_INMEMORY_VECTORS` (startup fails when false and Chroma is unavailable).

### Added
- SQLAlchemy engine + sessionmaker, WAL mode, per-request connections
- RQ worker + Redis rate limiting
- Alembic initial migration
- Structured JSON logs, optional Sentry
- `/metrics`, `/live`, `/ready`
- Multi-stage non-root Docker image with HEALTHCHECK and named volumes

### Rollback
Revert this release and restore `QUEUE_BACKEND=memory` plus an empty `API_KEY` if you need the previous unauthenticated local MVP behavior.
