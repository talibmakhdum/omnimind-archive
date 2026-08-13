from __future__ import annotations

from app.config import get_settings
from app.db import init_db
from app.rate_limit import reset_limiter_for_tests
from fastapi.testclient import TestClient


def test_search_rate_limit_returns_429(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_SEARCH_PER_MINUTE", "2")
    get_settings.cache_clear()
    reset_limiter_for_tests()
    init_db()
    from app.api import app

    # Settings on the already-imported app module are a snapshot; hit limiter via middleware
    # by patching the live settings object.
    get_settings().rate_limit_search_per_minute = 2
    client = TestClient(app)
    assert client.get("/search", params={"q": "a"}).status_code == 200
    assert client.get("/search", params={"q": "b"}).status_code == 200
    blocked = client.get("/search", params={"q": "c"})
    assert blocked.status_code == 429
