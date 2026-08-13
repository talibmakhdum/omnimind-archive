from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.db import init_db
from app.purge import purge_old_documents


def _insert(conn, message_id: str, ts: str, ingested: str) -> None:
    conn.execute(
        """
        INSERT INTO messages
        (message_id, session_id, source_platform, platform_message_id, timestamp,
         role, content, tokens, export_file, sha256, ingested_at)
        VALUES (?, 's', 'chatgpt', ?, ?, 'user', 'old or new', NULL, 'e.json', 'x', ?)
        """,
        (message_id, message_id, ts, ingested),
    )
    conn.execute(
        """
        INSERT INTO chunks
        (id, message_id, chunk_index, chunk_count, content, chunk_tokens,
         chunk_sha256, role, timestamp, source_platform, export_file)
        VALUES (?, ?, 0, 1, 'old or new', NULL, 'x', 'user', ?, 'chatgpt', 'e.json')
        """,
        (f"{message_id}:0", message_id, ts),
    )
    conn.commit()


def test_dry_run_does_not_delete(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "p.db"))
    init_db(conn)
    _insert(conn, "old", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z")
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    stats = purge_old_documents(conn, retention_days=30, dry_run=True, now=now, delete_vectors=False)
    assert stats["messages"] == 1
    assert stats["deleted_messages"] == 0
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    conn.close()


def test_execute_deletes_old_keeps_new_and_is_idempotent(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "p.db"))
    init_db(conn)
    _insert(conn, "old", "2020-01-01T00:00:00Z", "2020-01-01T00:00:00Z")
    _insert(conn, "new", "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z")
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    first = purge_old_documents(conn, retention_days=30, dry_run=False, now=now, delete_vectors=False)
    assert first["deleted_messages"] == 1
    ids = [r[0] for r in conn.execute("SELECT message_id FROM messages")]
    assert ids == ["new"]
    second = purge_old_documents(conn, retention_days=30, dry_run=False, now=now, delete_vectors=False)
    assert second["messages"] == 0
    assert second["deleted_messages"] == 0
    conn.close()
