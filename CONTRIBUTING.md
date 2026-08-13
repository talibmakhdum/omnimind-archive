# Contributing to OmniMind Archive

Thanks for helping make a privacy-first local archive better.

## Branching and PRs

- One theme per pull request (tests, CI, migrations, security, ops, docs, monitoring, SDK).
- Branch from `main` with a descriptive name (`feature/tests-seed`, `security/hash-api-keys`).
- Fill in `.github/PULL_REQUEST_TEMPLATE.md` and link an issue (`Closes #nnn`).
- Keep the default CI job under 10 minutes. Workflow YAML lives in `docs/github-actions/` (copy to `.github/workflows/` when the repo token allows it). Heavy benches: `docs/github-actions/benchmark.yml`.
- Do **not** change public HTTP routes without migration notes in `CHANGELOG.md` and `docs/api.md`.

## Commit messages

Use a Conventional Commits prefix:

- `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `ops:`, `security:`, `refactor:`, `chore:`

Examples:

- `test: add pytest fixtures and DB seeder`
- `security: store API keys as bcrypt hashes`

## Local setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
cd backend && PYTHONPATH=. pytest tests/ -v
```

Optional type/lint:

```bash
cd backend
ruff check app tests
mypy app --ignore-missing-imports
```

## Tests

- Put tests in `backend/tests/`.
- Use the autouse `DATA_DIR` isolation fixture; do not write to a developer’s real archive.
- Seed deterministic rows with `scripts/seed_test_db.py` / `backend/scripts/seed_test_db.py`.
- At least one test must cover SQLite read/write and the in-memory vector fallback.
- Set `BCRYPT_ROUNDS=4` in tests (already in `conftest.py`) so hashing stays fast.

## Migrations

```bash
cd backend
PYTHONPATH=. alembic upgrade head
PYTHONPATH=. alembic downgrade -1
```

Add columns with defaults. Never drop a column in the same release that still reads it. See `docs/migrations.md` and `docs/ops.md`.

## Security

- Hash API keys with bcrypt. Never commit `.env` or plaintext keys.
- Validate uploads by size and sniffed MIME type.
- Redact secrets in logs (`LOG_REDACT_SECRETS=true`).

## Review bar

Reviewers should confirm: CI green, tests for the new path, no public API break, and docs updated when behavior changes.
