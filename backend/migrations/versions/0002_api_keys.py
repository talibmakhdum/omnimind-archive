"""add hashed api_keys table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-13

Backward compatible: adds api_keys (key_hash only, never plaintext).
Downgrade drops the table; running processes still accept API_KEY / API_KEY_HASH env.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_revoked ON api_keys(revoked)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_api_keys_revoked")
    op.execute("DROP TABLE IF EXISTS api_keys")
