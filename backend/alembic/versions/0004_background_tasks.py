"""database-backed background task queue

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-15
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


DDL = [
    """
    CREATE TABLE IF NOT EXISTS background_tasks (
        id SERIAL PRIMARY KEY,
        task_type TEXT NOT NULL,
        payload JSONB,
        status TEXT DEFAULT 'pending',
        attempts INTEGER DEFAULT 0,
        max_attempts INTEGER DEFAULT 3,
        error TEXT,
        created_at TIMESTAMP NOT NULL,
        started_at TIMESTAMP,
        finished_at TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_background_tasks_status ON background_tasks(status, created_at ASC)",
]


def upgrade() -> None:
    for ddl in DDL:
        op.execute(ddl)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS background_tasks")
