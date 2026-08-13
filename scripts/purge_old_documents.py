#!/usr/bin/env python3
"""Purge documents older than retention_days. Commit-safe and idempotent.

Intended to be run via cron or GitHub Actions schedule.

Examples:
  python scripts/purge_old_documents.py --days 90
  python scripts/purge_old_documents.py --days 90 --execute
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.purge import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
