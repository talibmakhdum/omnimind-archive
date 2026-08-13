from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.config import get_settings


def _alembic_cfg(url: str) -> Config:
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_alembic_upgrade_downgrade_upgrade(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    url = get_settings().database_url
    cfg = _alembic_cfg(url)
    command.upgrade(cfg, "head")
    db = get_settings().db_path
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "messages" in tables
    assert "api_keys" in tables
    conn.close()

    command.downgrade(cfg, "0001")
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "api_keys" not in tables
    assert "messages" in tables
    conn.close()

    command.upgrade(cfg, "head")
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "api_keys" in tables
    conn.close()
