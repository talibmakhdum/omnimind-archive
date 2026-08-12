"""SQLite FTS5 full-text search."""

from __future__ import annotations

import sqlite3
from typing import Any


class BM25Engine:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def index_chunks(self, chunks: list[dict[str, Any]]) -> None:
        rows = [
            (
                chunk["message_id"],
                chunk.get("chunk_index", 0),
                chunk["content"],
                chunk["role"],
                chunk["timestamp"],
                chunk["source_platform"],
                chunk["export_file"],
            )
            for chunk in chunks
        ]
        self.conn.executemany(
            """
            INSERT INTO messages_fts
            (message_id, chunk_index, content, role, timestamp, source_platform, export_file)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def search(self, query: str, top_k: int = 50) -> list[dict[str, Any]]:
        query_escaped = query.replace('"', '""')
        try:
            results = self.conn.execute(
                """
                SELECT
                    message_id, chunk_index, content, role, timestamp,
                    source_platform, export_file, rank
                FROM messages_fts
                WHERE messages_fts MATCH ?
                ORDER BY rank ASC
                LIMIT ?
                """,
                (query_escaped, top_k),
            ).fetchall()
        except sqlite3.OperationalError:
            like = f"%{query}%"
            results = self.conn.execute(
                """
                SELECT message_id, chunk_index, content, role, timestamp,
                       source_platform, export_file, 0
                FROM messages_fts
                WHERE content LIKE ?
                LIMIT ?
                """,
                (like, top_k),
            ).fetchall()

        return [
            {
                "message_id": row[0],
                "chunk_index": row[1],
                "content": row[2],
                "role": row[3],
                "timestamp": row[4],
                "source_platform": row[5],
                "export_file": row[6],
                "bm25_score": abs(row[7] or 0),
            }
            for row in results
        ]
