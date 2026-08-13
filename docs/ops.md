# Operations: backup, restore, migrations, zero-downtime

## Backup

```bash
export DATA_DIR=.data
export CHROMA_PERSIST_DIR=.chroma
./scripts/backup_db.sh /var/backups/omnimind
```

The script uses `sqlite3 .backup` (safe with WAL) and tars the Chroma directory. Upload the resulting files to object storage:

```bash
aws s3 cp /var/backups/omnimind/archive-2026-08-13.db s3://my-bucket/omnimind/
aws s3 cp /var/backups/omnimind/chroma-2026-08-13.tgz s3://my-bucket/omnimind/
```

Cron example (daily 02:15 UTC):

```
15 2 * * * DATA_DIR=/data/sqlite CHROMA_PERSIST_DIR=/data/chroma /opt/omnimind/scripts/backup_db.sh /backups/omnimind
```

## Restore

```bash
./scripts/restore_db.sh /var/backups/omnimind/archive-2026-08-13.db /var/backups/omnimind/chroma-2026-08-13.tgz
```

Stop writers (API + worker) before swapping files, then start them again. `init_db` / Alembic will no-op if the schema is current.

## Logical export / import

JSONL format (`omnimind.archive.export`, schema 1.0) is portable across machines:

```bash
PYTHONPATH=backend python backend/scripts/export_archive.py /tmp/archive.jsonl
PYTHONPATH=backend python backend/scripts/import_archive.py /tmp/archive.jsonl
```

Import is `INSERT OR IGNORE` (idempotent). Re-embed after import if you need vectors on the destination.

## Migrations

See `docs/migrations.md`. Always backup first:

```bash
./scripts/backup_db.sh /var/backups/omnimind
cd backend && PYTHONPATH=. alembic upgrade head
```

Rollback one revision:

```bash
cd backend && PYTHONPATH=. alembic downgrade -1
```

## Zero-downtime deploys

SQLite is single-writer; “zero downtime” here means **no dropped requests** and **no unread schema**.

1. **Expand:** add tables/columns with defaults (`0002` style). Do not drop or rename yet.
2. Ship code that reads old + new and writes both (expand/contract).
3. Backfill in a job if needed.
4. Rolling restart: worker first (drain RQ), then API replicas.
5. **Contract** (drop legacy columns) only after every replica is on the new code.

Compose / systemd: start a new API container on a free port, health-check `/ready`, then flip the reverse proxy. Keep `DATA_DIR` and `CHROMA_PERSIST_DIR` on named volumes.

Breaking schema changes require a maintenance window or a dual-write phase. Document them in `CHANGELOG.md`.

## SQLite → Postgres (planned)

1. `python backend/scripts/export_archive.py dump.jsonl`
2. Provision Postgres; create a new Alembic branch **without** FTS5 virtual tables.
3. Load JSONL via a transform (map `messages` / `chunks` 1:1).
4. Rebuild lexical index (Postgres FTS) and re-embed into the chosen vector store.
5. Flip `database_url`, keep SQLite volume until the first successful backup on Postgres.

`pg_dump` / `pg_restore` become the backup path after the cutover.

```bash
pg_dump -Fc "$DATABASE_URL" -f omnimind.dump
pg_restore -d "$DATABASE_URL" omnimind.dump
```

## Retention

```bash
# dry-run
PURGE_ENABLED=true python scripts/purge_old_documents.py --days 90
# delete
PURGE_ENABLED=true python scripts/purge_old_documents.py --days 90 --execute
```

Refuse-to-run unless `PURGE_ENABLED=true` when `--execute` is set. Scheduled example: `docs/github-actions/purge.yml` and:

```
0 3 * * * PURGE_ENABLED=true DATA_DIR=/data/sqlite /opt/omnimind/.venv/bin/python /opt/omnimind/scripts/purge_old_documents.py --days 90 --execute
```

## Health

- Liveness: `GET /live`
- Readiness: `GET /ready` (503 if SQLite is down)
- Full: `GET /health` (DB + vector + queue length)
- Metrics: `GET /metrics`
