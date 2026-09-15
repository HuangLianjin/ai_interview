"""observability, feedback and eval tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


DDL = [
    """
    CREATE TABLE IF NOT EXISTS interview_runs (
        run_id TEXT PRIMARY KEY,
        session_id TEXT,
        user_id TEXT,
        entrypoint TEXT,
        status TEXT DEFAULT 'running',
        total_latency_ms DOUBLE PRECISION DEFAULT 0,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        error TEXT,
        started_at TIMESTAMP NOT NULL,
        finished_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS interview_run_steps (
        id SERIAL PRIMARY KEY,
        run_id TEXT NOT NULL,
        session_id TEXT,
        node_name TEXT NOT NULL,
        model TEXT,
        status TEXT DEFAULT 'success',
        latency_ms DOUBLE PRECISION DEFAULT 0,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        detail JSONB,
        error TEXT,
        created_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_feedback (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        session_id TEXT,
        target_type TEXT NOT NULL,
        target_id TEXT,
        rating INTEGER,
        tags JSONB,
        comment TEXT,
        created_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS eval_failures (
        id SERIAL PRIMARY KEY,
        case_id TEXT NOT NULL,
        category TEXT,
        question TEXT,
        answer TEXT,
        expected TEXT,
        actual TEXT,
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_interview_runs_session ON interview_runs(session_id, started_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_interview_runs_user ON interview_runs(user_id, started_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_interview_run_steps_run ON interview_run_steps(run_id, created_at ASC)",
    "CREATE INDEX IF NOT EXISTS idx_user_feedback_target ON user_feedback(target_type, target_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_user_feedback_session ON user_feedback(session_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_eval_failures_status ON eval_failures(status, created_at DESC)",
]


def upgrade() -> None:
    for ddl in DDL:
        op.execute(ddl)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS eval_failures")
    op.execute("DROP TABLE IF EXISTS user_feedback")
    op.execute("DROP TABLE IF EXISTS interview_run_steps")
    op.execute("DROP TABLE IF EXISTS interview_runs")
