"""Meaningful DB read/write + in-memory vector fallback coverage."""

from __future__ import annotations

import sqlite3

from app.db import init_db
from app.embedder import EmbeddingEngine, InMemoryVectorDB

from scripts.seed_test_db import seed_connection


def test_seed_fixture_roundtrip(db_conn):
    row = db_conn.execute(
        "SELECT content FROM messages WHERE message_id = ?", ("seed-msg-1",)
    ).fetchone()
    assert row is not None
    assert "machine learning" in row[0].lower()
    hashed = db_conn.execute("SELECT key_hash FROM api_keys WHERE name = 'seed'").fetchone()[0]
    assert hashed.startswith("$2")
    assert "test-seed-key" not in hashed


def test_db_write_then_read(tmp_path):
    path = str(tmp_path / "rw.db")
    conn = sqlite3.connect(path)
    init_db(conn)
    conn.execute(
        """
        INSERT INTO messages
        (message_id, session_id, source_platform, platform_message_id, timestamp,
         role, content, tokens, export_file, sha256, ingested_at)
        VALUES ('m1', 's', 'chatgpt', 'p', '2024-01-15T10:00:00Z', 'user',
                'vector fallback note', NULL, 'e.json', 'sha', '2024-01-15T10:00:00Z')
        """
    )
    conn.commit()
    got = conn.execute("SELECT content FROM messages WHERE message_id = 'm1'").fetchone()
    assert got[0] == "vector fallback note"
    conn.close()

    conn2 = sqlite3.connect(path)
    got2 = conn2.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert got2 == 1
    conn2.close()


def test_vector_fallback_write_query():
    engine = EmbeddingEngine(allow_fallback=True)
    engine.model = None
    store = InMemoryVectorDB()
    texts = ["machine learning basics", "unrelated cooking recipe"]
    embeddings, used_fallback = engine.embed_batch(texts)
    assert used_fallback is True
    store.add_embeddings(
        ["a", "b"],
        embeddings,
        [{"message_id": "a"}, {"message_id": "b"}],
        texts,
    )
    q, _ = engine.embed_single(texts[0])
    hits = store.query(q, top_k=2)
    assert hits["ids"][0][0] == "a"
    assert hits["documents"][0][0] == texts[0]
    assert store.ids == ["a", "b"]


def test_seed_function_is_deterministic(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "s.db"))
    init_db(conn)
    a = seed_connection(conn)
    b = seed_connection(conn)
    assert a == b
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 2
    conn.close()
