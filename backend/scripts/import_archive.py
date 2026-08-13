#!/usr/bin/env python3
"""Import OmniMind JSONL into SQLite (INSERT OR IGNORE)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db import connect, init_db
from app.exim import import_archive


def main() -> int:
    parser = argparse.ArgumentParser(description="Import archive JSONL")
    parser.add_argument("src", help="Input .jsonl path")
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    conn = connect(args.db or get_settings().db_path)
    try:
        init_db(conn)
        stats = import_archive(conn, args.src)
        print(stats)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
