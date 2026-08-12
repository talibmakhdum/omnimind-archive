"""SQLite schema: messages, FTS5, checkpoints, consent, audit, jobs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import get_settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT,
    source_platform TEXT NOT NULL,
    platform_message_id TEXT,
    timestamp TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER,
    export_file TEXT,
    sha256 TEXT,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    content TEXT NOT NULL,
    chunk_tokens INTEGER,
    chunk_sha256 TEXT,
    role TEXT,
    timestamp TEXT,
    source_platform TEXT,
    export_file TEXT
);

CREATE TABLE IF NOT EXISTS deduped_messages (
    dedupe_key TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    session_id TEXT NOT NULL,
    source_platform TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    export_file TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_checkpoints (
    export_filename TEXT PRIMARY KEY,
    source_platform TEXT NOT NULL,
    processed_offset INTEGER NOT NULL,
    last_message_timestamp TEXT NOT NULL,
    checkpoint_ts TEXT NOT NULL,
    total_processed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS consent_records (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source_platform TEXT NOT NULL,
    tos_url TEXT NOT NULL,
    tos_version TEXT NOT NULL,
    consent_given INTEGER NOT NULL,
    consent_details TEXT NOT NULL,
    export_filename TEXT,
    export_sha256 TEXT,
    ip_address TEXT,
    user_agent TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_consent_user_ts ON consent_records(user_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    progress_pct INTEGER DEFAULT 0,
    eta_seconds INTEGER DEFAULT 0,
    checkpoint TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    query TEXT NOT NULL,
    bm25_results TEXT,
    vector_results TEXT,
    created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    message_id,
    chunk_index,
    content,
    role,
    timestamp,
    source_platform,
    export_file,
    tokenize = 'porter'
);
"""


def connect(db_path: str | None = None) -> sqlite3.Connection:
    settings = get_settings()
    path = db_path or settings.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    own = conn is None
    conn = conn or connect()
    conn.executescript(SCHEMA)
    conn.commit()
    if own:
        return conn
    return conn
