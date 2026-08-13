# Database migrations

OmniMind uses [Alembic](https://alembic.sqlalchemy.org/) with SQLite (SQLAlchemy URL from `DATA_DIR`).

## Layout

- Config: `backend/alembic.ini`
- Env: `backend/migrations/env.py` (reads `get_settings().database_url`)
- Revisions: `backend/migrations/versions/`

| Revision | Purpose | Rollback |
|---|---|---|
| `0001` | Baseline tables (`messages`, `chunks`, FTS, jobs, consent) | Drops those tables (**data loss**) |
| `0002` | `api_keys` (bcrypt `key_hash` only) | `DROP TABLE api_keys` (env `API_KEY` / `API_KEY_HASH` still work) |

`app.db.SCHEMA` stays in sync so `init_db()` can create a fresh database without Alembic. `IF NOT EXISTS` keeps `upgrade head` safe on an already-initialized file.

## Local workflow

```bash
pip install -r backend/requirements.txt
cd backend
PYTHONPATH=. alembic current
PYTHONPATH=. alembic upgrade head
PYTHONPATH=. alembic downgrade -1
PYTHONPATH=. alembic upgrade head
```

Or via the helper (Alembic first, `SCHEMA` fallback):

```bash
python backend/scripts/init_db.py
```

Create a new revision after editing models/`SCHEMA`:

```bash
cd backend
PYTHONPATH=. alembic revision -m "add_column_x"
# edit migrations/versions/*_add_column_x.py
PYTHONPATH=. alembic upgrade head
```

## Rules (zero-downtime friendly)

1. **Expand/contract.** Add a nullable column or a new table first. Deploy code that writes both old and new. Backfill. Switch readers. Drop the old column in a later release.
2. **Never** rewrite SQLite files in place as a “migration”.
3. Document every revision’s `downgrade()` and any data you cannot restore.
4. Production: take a SQLite `.backup` (see `scripts/backup_db.sh`) before `upgrade`.

## Rollback notes

```bash
# one step
cd backend && PYTHONPATH=. alembic downgrade -1

# back to baseline schema
PYTHONPATH=. alembic downgrade 0001
```

`0002` downgrade removes stored hashed keys only. Processes still authenticate with `API_KEY` (hashed in memory at boot) or `API_KEY_HASH`.

## Postgres (later)

Set `database_url` to `postgresql+psycopg://…` when the engine is swapped. Do **not** point Alembic at Postgres and SQLite with the same revision history without a dedicated fork — FTS5 is SQLite-specific. See `docs/ops.md` for dump/transform notes.
