"""Bearer API key authentication with bcrypt-hashed storage."""

from __future__ import annotations

import hashlib
import os
import secrets
import threading
import uuid
from typing import Any

import bcrypt
from fastapi import Header, HTTPException

from app.config import get_settings

_lock = threading.Lock()
_env_key_hash: str | None = None
_verified_token_digests: set[str] = set()


def _rounds() -> int:
    settings = get_settings()
    env_rounds = os.environ.get("BCRYPT_ROUNDS")
    if env_rounds:
        return max(4, int(env_rounds))
    return max(4, int(settings.bcrypt_rounds))


def hash_api_key(api_key: str, rounds: int | None = None) -> str:
    """Return a bcrypt hash. Never persist the plaintext key."""
    if not api_key:
        raise ValueError("api_key must be non-empty")
    cost = _rounds() if rounds is None else rounds
    return bcrypt.hashpw(api_key.encode("utf-8"), bcrypt.gensalt(rounds=cost)).decode("utf-8")


def verify_api_key(api_key: str, hashed: str) -> bool:
    if not api_key or not hashed:
        return False
    try:
        return bcrypt.checkpw(api_key.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def token_digest(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def reset_auth_cache() -> None:
    global _env_key_hash
    with _lock:
        _env_key_hash = None
        _verified_token_digests.clear()


def configured_env_hash() -> str | None:
    """Bcrypt hash of the process API key (from API_KEY_HASH or hashed API_KEY)."""
    global _env_key_hash
    settings = get_settings()
    if settings.api_key_hash:
        return settings.api_key_hash
    if not settings.api_key:
        return None
    with _lock:
        if _env_key_hash is None:
            _env_key_hash = hash_api_key(settings.api_key)
        return _env_key_hash


def generate_api_key() -> str:
    return "omk_" + secrets.token_urlsafe(32)


def store_api_key(conn: Any, name: str, api_key: str | None = None) -> dict[str, str]:
    """Insert a hashed API key. Returns the plaintext once for the caller."""
    from app.audit import now_iso

    plaintext = api_key or generate_api_key()
    key_hash = hash_api_key(plaintext)
    key_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO api_keys (id, name, key_hash, created_at, last_used_at, revoked)
        VALUES (?, ?, ?, ?, NULL, 0)
        """,
        (key_id, name, key_hash, now_iso()),
    )
    conn.commit()
    return {"id": key_id, "name": name, "api_key": plaintext, "key_hash": key_hash}


def list_stored_api_keys(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, name, created_at, last_used_at, revoked FROM api_keys ORDER BY created_at"
    ).fetchall()
    return [
        {
            "id": row[0],
            "name": row[1],
            "created_at": row[2],
            "last_used_at": row[3],
            "revoked": bool(row[4]),
        }
        for row in rows
    ]


def revoke_api_key(conn: Any, key_id: str) -> bool:
    cur = conn.execute("UPDATE api_keys SET revoked = 1 WHERE id = ?", (key_id,))
    conn.commit()
    with _lock:
        _verified_token_digests.clear()
    return cur.rowcount > 0


def _verify_against_db(api_key: str) -> bool:
    from app.audit import now_iso
    from app.db import get_connection

    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, key_hash FROM api_keys WHERE revoked = 0"
            ).fetchall()
            for row in rows:
                if verify_api_key(api_key, row[1]):
                    conn.execute(
                        "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                        (now_iso(), row[0]),
                    )
                    return True
    except Exception:
        return False
    return False


def authenticate_token(token: str) -> bool:
    digest = token_digest(token)
    with _lock:
        if digest in _verified_token_digests:
            return True

    env_hash = configured_env_hash()
    if env_hash and verify_api_key(token, env_hash):
        with _lock:
            _verified_token_digests.add(digest)
        return True

    if _verify_against_db(token):
        with _lock:
            _verified_token_digests.add(digest)
        return True
    return False


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = (settings.api_key or "").strip()
    required = settings.auth_required or bool(expected) or bool(settings.api_key_hash)
    if not required:
        return
    if not expected and not settings.api_key_hash:
        # Auth required but only DB-stored keys may exist.
        pass
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not expected and not settings.api_key_hash:
        # Fall through to DB-only verification.
        if authenticate_token(token):
            return
        raise HTTPException(status_code=401, detail="Invalid API key")
    if authenticate_token(token):
        return
    raise HTTPException(status_code=401, detail="Invalid API key")
