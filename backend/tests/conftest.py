from __future__ import annotations

import os

os.environ.setdefault("ALLOW_INMEMORY_VECTORS", "true")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("AUTH_REQUIRED", "true")
os.environ.setdefault("QUEUE_BACKEND", "memory")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("SENTRY_DSN", "")

import pytest
from app.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("CHECKPOINT_DIR", str(tmp_path / "data" / "checkpoints"))
    monkeypatch.setenv("FAILED_EXPORTS_DIR", str(tmp_path / "data" / "failed"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "data" / "uploads"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
