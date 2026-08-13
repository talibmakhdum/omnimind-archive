"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op

from app.db import SCHEMA

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    raw = conn.connection
    dbapi = getattr(raw, "dbapi_connection", raw)
    dbapi.executescript(SCHEMA)


def downgrade() -> None:
    for stmt in (
        "DROP TABLE IF EXISTS search_jobs",
        "DROP TABLE IF EXISTS ingest_jobs",
        "DROP TABLE IF EXISTS consent_records",
        "DROP TABLE IF EXISTS ingest_checkpoints",
        "DROP TABLE IF EXISTS deduped_messages",
        "DROP TABLE IF EXISTS chunks",
        "DROP TABLE IF EXISTS messages",
        "DROP TABLE IF EXISTS messages_fts",
    ):
        op.execute(stmt)
