#!/usr/bin/env python3
"""Lightweight test DB seeder used by pytest fixtures.

Keep fast and deterministic. Inserts a handful of messages/chunks and one
bcrypt-hashed API key. Never writes plaintext keys.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.audit import now_iso  # noqa: E402
from app.auth import hash_api_key  # noqa: E402
from app.config import ensure_dirs, get_settings  # noqa: E402
from app.db import init_db  # noqa: E402

SEED_API_KEY = "test-seed-key"
SEED_MESSAGES = (
    {
        "message_id": "seed-msg-1",
        "session_id": "seed-sess",
        "source_platform": "chatgpt",
        "platform_message_id": "p1",
        "timestamp": "2024-01-15T10:00:00Z",
        "role": "user",
        "content": "What is machine learning?",
        "export_file": "seed.json",
        "sha256": "abc123",
    },
    {
        "message_id": "seed-msg-2",
        "session_id": "seed-sess",
        "source_platform": "chatgpt",
        "platform_message_id": "p2",
        "timestamp": "2024-01-15T10:01:00Z",
        "role": "assistant",
        "content": "Machine learning learns patterns from data.",
        "export_file": "seed.json",
        "sha256": "def456",
    },
)


def seed_connection(conn: sqlite3.Connection, api_key: str = SEED_API_KEY) -> dict[str, int]:
    init_db(conn)
    ingested = now_iso()
    for msg in SEED_MESSAGES:
        conn.execute(
            """
            INSERT OR REPLACE INTO messages
            (message_id, session_id, source_platform, platform_message_id, timestamp,
             role, content, tokens, export_file, sha256, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg["message_id"],
                msg["session_id"],
                msg["source_platform"],
                msg["platform_message_id"],
                msg["timestamp"],
                msg["role"],
                msg["content"],
                None,
                msg["export_file"],
                msg["sha256"],
                ingested,
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO chunks
            (id, message_id, chunk_index, chunk_count, content, chunk_tokens,
             chunk_sha256, role, timestamp, source_platform, export_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{msg['message_id']}:0",
                msg["message_id"],
                0,
                1,
                msg["content"],
                None,
                msg["sha256"],
                msg["role"],
                msg["timestamp"],
                msg["source_platform"],
                msg["export_file"],
            ),
        )
        conn.execute(
            """
            INSERT INTO messages_fts
            (message_id, chunk_index, content, role, timestamp, source_platform, export_file)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg["message_id"],
                0,
                msg["content"],
                msg["role"],
                msg["timestamp"],
                msg["source_platform"],
                msg["export_file"],
            ),
        )
    conn.execute("DELETE FROM api_keys WHERE name = ?", ("seed",))
    conn.execute(
        """
        INSERT INTO api_keys (id, name, key_hash, created_at, last_used_at, revoked)
        VALUES (?, ?, ?, ?, NULL, 0)
        """,
        ("seed-key-id", "seed", hash_api_key(api_key), ingested),
    )
    conn.commit()
    return {"messages": len(SEED_MESSAGES), "api_keys": 1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a deterministic test database")
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    settings = get_settings()
    ensure_dirs(settings)
    path = args.db or settings.db_path
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        stats = seed_connection(conn)
        print(f"Seeded {path}: {stats}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
