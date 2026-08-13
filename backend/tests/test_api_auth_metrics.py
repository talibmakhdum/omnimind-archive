from __future__ import annotations

from app.config import get_settings
from app.db import init_db
from fastapi.testclient import TestClient


def _client():
    get_settings.cache_clear()
    init_db()
    from app.api import app

    return TestClient(app)


def test_health_and_metrics_public():
    client = _client()
    h = client.get("/health")
    assert h.status_code == 200
    m = client.get("/metrics")
    assert m.status_code == 200
    assert "omnimind" in m.text or m.headers["content-type"].startswith("text/plain")
    assert client.get("/live").status_code == 200
    assert client.get("/ready").status_code == 200


def test_protected_endpoints_require_api_key():
    client = _client()
    assert client.post("/query", json={"q": "hi"}).status_code == 401
    assert client.get("/admin/stats").status_code == 401
    headers = {"Authorization": "Bearer test-key"}
    assert client.get("/admin/stats", headers=headers).status_code == 200
    ok = client.post("/query", json={"q": "machine"}, headers=headers)
    assert ok.status_code == 200


def test_ingest_without_key_rejected(tmp_path):
    client = _client()
    sample = tmp_path / "e.json"
    sample.write_text('{"conversations":[]}')
    with sample.open("rb") as fh:
        resp = client.post(
            "/ingest",
            data={"consent_given": "true", "source_platform": "chatgpt"},
            files={"file": ("e.json", fh, "application/json")},
        )
    assert resp.status_code == 401
