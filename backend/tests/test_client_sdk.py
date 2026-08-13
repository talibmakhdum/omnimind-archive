from __future__ import annotations

import sys
from pathlib import Path

from app.config import get_settings
from app.db import init_db
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sdk"))

from omnimind import OmniMindClient  # noqa: E402


def test_sdk_health_and_search():
    get_settings.cache_clear()
    init_db()
    from app.api import app

    http = TestClient(app)
    client = OmniMindClient(base_url="", api_key="test-key", client=http)
    health = client.health()
    assert health["status"] in {"ok", "degraded"}
    stats = client.admin_stats()
    assert "messages" in stats
    result = client.search("machine", k=3)
    assert "results" in result
