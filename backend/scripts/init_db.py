#!/usr/bin/env python3
"""Initialize SQLite schema via Alembic, with a direct SCHEMA fallback."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import ensure_dirs, get_settings  # noqa: E402
from app.db import init_db  # noqa: E402


def main() -> None:
    settings = get_settings()
    ensure_dirs(settings)
    alembic_ini = ROOT / "alembic.ini"
    if alembic_ini.exists():
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
            cwd=str(ROOT),
            check=False,
        )
        if result.returncode == 0:
            print(f"Alembic upgraded {settings.db_path}")
            return
        print("Alembic failed; applying SCHEMA fallback", file=sys.stderr)
    init_db()
    print(f"Initialized {settings.db_path}")


if __name__ == "__main__":
    main()
