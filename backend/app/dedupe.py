"""Idempotent dedupe with fingerprinting and checkpoints."""

from __future__ import annotations

import hashlib
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Optional

NS_URL = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def canonicalize_content(content: str) -> str:
    content = unicodedata.normalize("NFKC", content)
    content = content.replace("\r\n", "\n")
    while "\n\n\n" in content:
        content = content.replace("\n\n\n", "\n\n")
    lines = [line.strip() for line in content.split("\n")]
    return "\n".join(lines).strip()


def canonicalize_timestamp(timestamp: str) -> str:
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_fingerprint(
    normalized_content: str,
    normalized_timestamp: str,
    source_platform: str,
) -> str:
    message = f"{normalized_content}|{normalized_timestamp}|{source_platform}"
    return hashlib.sha256(message.encode()).hexdigest()


def compute_dedupe_key(fingerprint: str, session_id: str) -> str:
    return f"{fingerprint}|{session_id}"


def compute_message_id(fingerprint: str, session_id: str) -> str:
    return str(uuid.uuid5(NS_URL, f"{fingerprint}|{session_id}"))


class DedupeEngine:
    def __init__(self, db_connection):
        self.db = db_connection

    def dedupe(
        self,
        content: str,
        timestamp: str,
        session_id: str,
        source_platform: str,
        platform_message_id: Optional[str],
        export_file: str,
        force_ingest: bool = False,
    ) -> tuple[str, bool]:
        normalized_content = canonicalize_content(content)
        normalized_timestamp = canonicalize_timestamp(timestamp)
        fingerprint = compute_fingerprint(
            normalized_content, normalized_timestamp, source_platform
        )
        dedupe_key = compute_dedupe_key(fingerprint, session_id)

        existing = self.db.execute(
            "SELECT message_id FROM deduped_messages WHERE dedupe_key = ?",
            (dedupe_key,),
        ).fetchone()
        if existing and not force_ingest:
            return existing[0], True

        message_id = platform_message_id or compute_message_id(fingerprint, session_id)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.execute(
            """
            INSERT OR REPLACE INTO deduped_messages
            (dedupe_key, message_id, fingerprint, session_id, source_platform,
             timestamp, ingested_at, export_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dedupe_key,
                message_id,
                fingerprint,
                session_id,
                source_platform,
                normalized_timestamp,
                now,
                export_file,
            ),
        )
        self.db.commit()
        return message_id, False

    def save_checkpoint(
        self,
        export_filename: str,
        source_platform: str,
        processed_offset: int,
        last_message_timestamp: str,
        total_processed: int,
    ) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.execute(
            """
            INSERT OR REPLACE INTO ingest_checkpoints
            (export_filename, source_platform, processed_offset,
             last_message_timestamp, checkpoint_ts, total_processed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                export_filename,
                source_platform,
                processed_offset,
                last_message_timestamp,
                now,
                total_processed,
            ),
        )
        self.db.commit()

    def load_checkpoint(self, export_filename: str) -> Optional[dict]:
        row = self.db.execute(
            """
            SELECT processed_offset, last_message_timestamp, total_processed
            FROM ingest_checkpoints WHERE export_filename = ?
            """,
            (export_filename,),
        ).fetchone()
        if row:
            return {
                "processed_offset": row[0],
                "last_message_timestamp": row[1],
                "total_processed": row[2],
            }
        return None
