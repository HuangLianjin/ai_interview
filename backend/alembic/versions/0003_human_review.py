"""human review, appeals and audit tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-15
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


DDL = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user'",
    """
    CREATE TABLE IF NOT EXISTS score_appeals (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        question_index INTEGER NOT NULL,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        original_total DOUBLE PRECISION,
        revised_total DOUBLE PRECISION,
        admin_note TEXT,
        created_at TIMESTAMP NOT NULL,
        resolved_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        action TEXT NOT NULL,
        target_type TEXT,
        target_id TEXT,
        detail JSONB,
        created_at TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_score_appeals_status ON score_appeals(status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_score_appeals_user ON score_appeals(user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC)",
]


def upgrade() -> None:
    for ddl in DDL:
        op.execute(ddl)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs")
    op.execute("DROP TABLE IF EXISTS score_appeals")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS role")
