#!/usr/bin/env python3
"""Initialize SQLite schema."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import ensure_dirs, get_settings  # noqa: E402
from app.db import connect, init_db  # noqa: E402


def main() -> None:
    settings = get_settings()
    ensure_dirs(settings)
    init_db(connect(settings.db_path))
    print(f"Initialized {settings.db_path}")


if __name__ == "__main__":
    main()
