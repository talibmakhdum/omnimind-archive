"""Retention purge: remove documents older than retention_days.

Commit-safe and idempotent. Intended for cron or GitHub Actions.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings
from app.db import connect, init_db

logger = logging.getLogger(__name__)

EXPORT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _cutoff_iso(retention_days: int, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return (current - timedelta(days=retention_days)).strftime(EXPORT_FORMAT)


def _select_old_ids(conn: sqlite3.Connection, cutoff: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT message_id FROM messages
        WHERE timestamp < ? OR ingested_at < ?
        """,
        (cutoff, cutoff),
    ).fetchall()
    return [row[0] for row in rows]


def purge_old_documents(
    conn: sqlite3.Connection,
    retention_days: int | None = None,
    dry_run: bool = True,
    now: datetime | None = None,
    delete_vectors: bool = True,
) -> dict[str, Any]:
    """Delete messages (and related rows) older than the retention window."""
    settings = get_settings()
    days = settings.retention_days if retention_days is None else retention_days
    if days < 0:
        raise ValueError("retention_days must be >= 0")
    cutoff = _cutoff_iso(days, now)
    ids = _select_old_ids(conn, cutoff)
    chunk_rows = conn.execute(
        f"SELECT id FROM chunks WHERE message_id IN ({','.join('?' * len(ids))})",
        ids,
    ).fetchall() if ids else []
    chunk_ids = [row[0] for row in chunk_rows]
    stats: dict[str, Any] = {
        "dry_run": dry_run,
        "retention_days": days,
        "cutoff": cutoff,
        "messages": len(ids),
        "chunks": len(chunk_ids),
        "deleted_messages": 0,
        "deleted_chunks": 0,
        "deleted_fts": 0,
        "deleted_dedupe": 0,
        "deleted_vectors": 0,
    }
    if dry_run or not ids:
        return stats

    placeholders = ",".join("?" * len(ids))
    try:
        conn.execute("BEGIN")
        stats["deleted_chunks"] = conn.execute(
            f"DELETE FROM chunks WHERE message_id IN ({placeholders})", ids
        ).rowcount
        try:
            stats["deleted_fts"] = conn.execute(
                f"DELETE FROM messages_fts WHERE message_id IN ({placeholders})", ids
            ).rowcount
        except sqlite3.OperationalError:
            stats["deleted_fts"] = 0
        stats["deleted_dedupe"] = conn.execute(
            f"DELETE FROM deduped_messages WHERE message_id IN ({placeholders})", ids
        ).rowcount
        stats["deleted_messages"] = conn.execute(
            f"DELETE FROM messages WHERE message_id IN ({placeholders})", ids
        ).rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    if delete_vectors and chunk_ids:
        try:
            from app.ingest import get_shared_engines

            _, vec = get_shared_engines()
            if hasattr(vec, "delete_ids"):
                vec.delete_ids(chunk_ids)
                stats["deleted_vectors"] = len(chunk_ids)
        except Exception:
            logger.warning("Vector delete skipped; rebuild the index after purge")

    try:
        from app.metrics import PURGE_DELETED

        PURGE_DELETED.labels(entity="messages").inc(float(stats["deleted_messages"]))
        PURGE_DELETED.labels(entity="chunks").inc(float(stats["deleted_chunks"]))
    except Exception:
        pass
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Purge documents older than retention_days")
    parser.add_argument("--days", type=int, default=None, help="Override RETENTION_DAYS")
    parser.add_argument("--db", default=None, help="SQLite path (default: settings.db_path)")
    parser.add_argument("--execute", action="store_true", help="Actually delete (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run (default)")
    args = parser.parse_args(argv)

    settings = get_settings()
    if not settings.purge_enabled and args.execute and not args.dry_run:
        logger.error("PURGE_ENABLED=false; refusing to delete. Set PURGE_ENABLED=true or use --dry-run.")
        return 2

    db_path = args.db or settings.db_path
    conn = connect(db_path)
    try:
        init_db(conn)
        dry_run = not args.execute or args.dry_run
        stats = purge_old_documents(conn, retention_days=args.days, dry_run=dry_run)
        print(stats)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
