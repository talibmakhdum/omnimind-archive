#!/usr/bin/env python3
"""Export messages + chunks to OmniMind JSONL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db import connect
from app.exim import export_archive


def main() -> int:
    parser = argparse.ArgumentParser(description="Export archive to JSONL")
    parser.add_argument("dest", help="Output .jsonl path")
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    conn = connect(args.db or get_settings().db_path)
    try:
        stats = export_archive(conn, args.dest)
        print(stats)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
