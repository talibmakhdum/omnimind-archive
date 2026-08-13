from __future__ import annotations

import sqlite3

from app.auth import (
    authenticate_token,
    hash_api_key,
    reset_auth_cache,
    store_api_key,
    verify_api_key,
)
from app.db import init_db
from fastapi.testclient import TestClient


def test_hash_is_bcrypt_and_not_plaintext():
    raw = "super-secret-key"
    hashed = hash_api_key(raw, rounds=4)
    assert hashed != raw
    assert hashed.startswith("$2")
    assert raw not in hashed
    assert verify_api_key(raw, hashed) is True
    assert verify_api_key("wrong", hashed) is False


def test_db_stores_hash_not_plaintext(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "keys.db"))
    init_db(conn)
    created = store_api_key(conn, "ci", "plain-once")
    assert created["api_key"] == "plain-once"
    row = conn.execute("SELECT key_hash FROM api_keys WHERE id = ?", (created["id"],)).fetchone()
    assert row is not None
    stored = row[0]
    assert stored != "plain-once"
    assert stored.startswith("$2")
    assert verify_api_key("plain-once", stored)
    conn.close()


def test_authenticate_against_env_hash():
    reset_auth_cache()
    assert authenticate_token("test-key") is True
    assert authenticate_token("nope") is False


def test_admin_api_key_roundtrip():
    from app.config import get_settings
    from app.db import init_db as _init

    get_settings.cache_clear()
    _init()
    from app.api import app

    client = TestClient(app)
    headers = {"Authorization": "Bearer test-key"}
    created = client.post("/admin/api-keys", json={"name": "robot"}, headers=headers)
    assert created.status_code == 200
    body = created.json()
    assert body["api_key"].startswith("omk_")
    listed = client.get("/admin/api-keys", headers=headers)
    assert listed.status_code == 200
    assert any(k["name"] == "robot" for k in listed.json()["keys"])
    assert all("key_hash" not in k and "api_key" not in k for k in listed.json()["keys"])
