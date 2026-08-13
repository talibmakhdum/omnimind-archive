# Changelog

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
