"""Thread-safe SQLite access via SQLAlchemy + WAL."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

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

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_api_keys_revoked ON api_keys(revoked);

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

_engines: dict[str, Engine] = {}
_sessionmakers: dict[str, sessionmaker] = {}


def _apply_pragmas(dbapi_conn) -> None:
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA busy_timeout=30000")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


def _on_connect(dbapi_conn, _connection_record=None) -> None:
    _apply_pragmas(dbapi_conn)


def get_engine(db_path: str | None = None) -> Engine:
    settings = get_settings()
    path = db_path or settings.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if path not in _engines:
        engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=NullPool,
        )
        event.listen(engine, "connect", _on_connect)
        _engines[path] = engine
        _sessionmakers[path] = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _engines[path]


def get_sessionmaker(db_path: str | None = None) -> sessionmaker:
    get_engine(db_path)
    return _sessionmakers[db_path or get_settings().db_path]


def get_session(db_path: str | None = None) -> Session:
    return get_sessionmaker(db_path)()


def connect(db_path: str | None = None) -> sqlite3.Connection:
    settings = get_settings()
    path = db_path or settings.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


@contextmanager
def get_connection(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    raw = connect(db_path)
    try:
        yield raw
        raw.commit()
    except Exception:
        try:
            raw.rollback()
        except sqlite3.Error:
            pass
        raise
    finally:
        raw.close()


def init_db(conn: sqlite3.Connection | None = None, db_path: str | None = None):
    if conn is not None:
        conn.executescript(SCHEMA)
        _apply_pragmas(conn)
        conn.commit()
        return conn
    fresh = connect(db_path)
    try:
        fresh.executescript(SCHEMA)
        fresh.commit()
    finally:
        fresh.close()
    return get_engine(db_path)


def db_health(db_path: str | None = None) -> bool:
    try:
        with get_connection(db_path) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


def wal_mode(db_path: str | None = None) -> str:
    with get_connection(db_path) as conn:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        return str(row[0] if row else "")
