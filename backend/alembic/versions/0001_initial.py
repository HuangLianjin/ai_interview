"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-31
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = [
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT 'default_user',
        title TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        mode TEXT NOT NULL,
        resume_filename TEXT,
        resume_content TEXT,
        job_description TEXT,
        company_info TEXT,
        interview_plan JSONB,
        question_count INTEGER DEFAULT 0,
        max_questions INTEGER DEFAULT 5,
        status TEXT DEFAULT 'active',
        pinned BOOLEAN DEFAULT FALSE,
        candidate_profile JSONB,
        series_id TEXT,
        round_index INTEGER DEFAULT 1,
        round_type TEXT DEFAULT 'tech_initial',
        parent_session_id TEXT REFERENCES sessions(session_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        question_index INTEGER DEFAULT 0,
        timestamp TIMESTAMP NOT NULL,
        audio_url TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_profile (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL UNIQUE,
        profile_data JSONB NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS resume_results (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        result_type TEXT NOT NULL,
        resume_content TEXT NOT NULL,
        job_description TEXT,
        session_ids JSONB,
        include_profile BOOLEAN DEFAULT FALSE,
        result_data JSONB NOT NULL,
        created_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS generated_resumes (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        optimization_result_id INTEGER,
        job_description TEXT,
        content TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        phone VARCHAR(20) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        nickname VARCHAR(50) DEFAULT '',
        avatar TEXT DEFAULT 'teal',
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sms_codes (
        id SERIAL PRIMARY KEY,
        phone VARCHAR(20) NOT NULL,
        code VARCHAR(10) NOT NULL,
        used BOOLEAN DEFAULT FALSE,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS answer_scores (
        id SERIAL PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        question_index INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        answer_text TEXT NOT NULL,
        dimensions JSONB,
        total FLOAT,
        comment TEXT,
        created_at TIMESTAMP NOT NULL,
        UNIQUE(session_id, question_index)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_session_updated ON sessions(updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_session_status ON sessions(status)",
    "CREATE INDEX IF NOT EXISTS idx_session_mode ON sessions(mode)",
    "CREATE INDEX IF NOT EXISTS idx_session_user ON sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_session_user_pinned ON sessions(user_id, pinned DESC, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_session_series ON sessions(series_id)",
    "CREATE INDEX IF NOT EXISTS idx_session_parent ON sessions(parent_session_id)",
    "CREATE INDEX IF NOT EXISTS idx_message_session ON messages(session_id, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_message_timestamp ON messages(timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_resume_results_user ON resume_results(user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_resume_results_type ON resume_results(result_type)",
    "CREATE INDEX IF NOT EXISTS idx_generated_resumes_user ON generated_resumes(user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_sms_codes_phone ON sms_codes(phone, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_answer_scores_session ON answer_scores(session_id, question_index)",
]


def upgrade() -> None:
    for ddl in DDL:
        op.execute(ddl)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS answer_scores")
    op.execute("DROP TABLE IF EXISTS sms_codes")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS generated_resumes")
    op.execute("DROP TABLE IF EXISTS resume_results")
    op.execute("DROP TABLE IF EXISTS user_profile")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS sessions")