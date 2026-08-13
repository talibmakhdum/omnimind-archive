from __future__ import annotations

import os
import sqlite3
from pathlib import Path

os.environ.setdefault("ALLOW_INMEMORY_VECTORS", "true")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("AUTH_REQUIRED", "true")
os.environ.setdefault("QUEUE_BACKEND", "memory")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("SENTRY_DSN", "")
os.environ.setdefault("BCRYPT_ROUNDS", "4")
os.environ.setdefault("PURGE_ENABLED", "true")

import pytest
from app.auth import reset_auth_cache
from app.config import get_settings
from app.db import init_db
from app.rate_limit import reset_limiter_for_tests


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("CHECKPOINT_DIR", str(tmp_path / "data" / "checkpoints"))
    monkeypatch.setenv("FAILED_EXPORTS_DIR", str(tmp_path / "data" / "failed"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "data" / "uploads"))
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    get_settings.cache_clear()
    reset_auth_cache()
    reset_limiter_for_tests()
    yield
    get_settings.cache_clear()
    reset_auth_cache()


@pytest.fixture
def db_conn(tmp_path):
    path = tmp_path / "seeded.db"
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    from scripts.seed_test_db import seed_connection

    seed_connection(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_export_path() -> Path:
    return Path(__file__).resolve().parents[2] / "samples" / "chatgpt_sample.json"
