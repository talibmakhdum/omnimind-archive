#!/bin/sh
set -eu
python scripts/init_db.py || true
exec uvicorn app.api:app --host 0.0.0.0 --port 8000
