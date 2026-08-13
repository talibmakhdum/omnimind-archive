"""Archive export/import (JSONL). Additive, non-destructive import."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TextIO

SCHEMA_VERSION = "1.0"
EXPORT_KIND = "omnimind.archive.export"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def export_archive(conn: sqlite3.Connection, dest: Path | str | TextIO) -> dict[str, int]:
    close = False
    if isinstance(dest, (str, Path)):
        path = Path(dest)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh: TextIO = path.open("w", encoding="utf-8")
        close = True
    else:
        fh = dest
    counts = {"messages": 0, "chunks": 0}
    try:
        header = {
            "type": "manifest",
            "kind": EXPORT_KIND,
            "schema_version": SCHEMA_VERSION,
            "exported_at": _now(),
        }
        fh.write(json.dumps(header, ensure_ascii=False) + "\n")
        for row in conn.execute("SELECT * FROM messages"):
            rec = {"type": "message", **dict(row)}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts["messages"] += 1
        for row in conn.execute("SELECT * FROM chunks"):
            rec = {"type": "chunk", **dict(row)}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts["chunks"] += 1
    finally:
        if close:
            fh.close()
    return counts


def _iter_records(src: Path | str | Iterable[str]) -> Iterable[dict[str, Any]]:
    if isinstance(src, (str, Path)):
        with Path(src).open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)
        return
    for line in src:
        line = line.strip()
        if line:
            yield json.loads(line)


def import_archive(conn: sqlite3.Connection, src: Path | str | Iterable[str]) -> dict[str, int]:
    counts = {"messages": 0, "chunks": 0, "skipped": 0}
    for rec in _iter_records(src):
        kind = rec.get("type")
        if kind == "manifest":
            continue
        if kind == "message":
            conn.execute(
                """
                INSERT OR IGNORE INTO messages
                (message_id, session_id, source_platform, platform_message_id, timestamp,
                 role, content, tokens, export_file, sha256, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec["message_id"],
                    rec.get("session_id"),
                    rec["source_platform"],
                    rec.get("platform_message_id"),
                    rec["timestamp"],
                    rec["role"],
                    rec["content"],
                    rec.get("tokens"),
                    rec.get("export_file"),
                    rec.get("sha256"),
                    rec.get("ingested_at") or _now(),
                ),
            )
            counts["messages"] += 1
        elif kind == "chunk":
            conn.execute(
                """
                INSERT OR IGNORE INTO chunks
                (id, message_id, chunk_index, chunk_count, content, chunk_tokens,
                 chunk_sha256, role, timestamp, source_platform, export_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.get("id") or f"{rec['message_id']}:{rec.get('chunk_index', 0)}",
                    rec["message_id"],
                    rec.get("chunk_index", 0),
                    rec.get("chunk_count", 1),
                    rec["content"],
                    rec.get("chunk_tokens"),
                    rec.get("chunk_sha256"),
                    rec.get("role"),
                    rec.get("timestamp"),
                    rec.get("source_platform"),
                    rec.get("export_file"),
                ),
            )
            conn.execute(
                """
                INSERT INTO messages_fts
                (message_id, chunk_index, content, role, timestamp, source_platform, export_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec["message_id"],
                    rec.get("chunk_index", 0),
                    rec["content"],
                    rec.get("role"),
                    rec.get("timestamp"),
                    rec.get("source_platform"),
                    rec.get("export_file"),
                ),
            )
            counts["chunks"] += 1
        else:
            counts["skipped"] += 1
    conn.commit()
    return counts
