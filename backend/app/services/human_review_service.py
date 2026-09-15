"""人机协同：评分申诉、管理员复核与审计日志。"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from app.database.base import db_manager

logger = logging.getLogger(__name__)

_tables_ready = False
_lock = asyncio.Lock()


async def ensure_review_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    async with _lock:
        if _tables_ready:
            return
        ddl = [
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
        try:
            async with db_manager.get_connection() as conn:
                for sql in ddl:
                    await conn.execute(sql)
            _tables_ready = True
        except Exception as e:
            logger.warning("初始化人机协同表失败: %s", e)


async def is_admin(user_id: str) -> bool:
    await ensure_review_tables()
    async with db_manager.get_connection() as conn:
        role = await conn.fetchval(
            "SELECT role FROM users WHERE id = $1::int",
            int(user_id),
        )
    return role in ("admin", "super_admin")


async def write_audit(
    user_id: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    await ensure_review_tables()
    async with db_manager.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO audit_logs (user_id, action, target_type, target_id, detail, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            user_id,
            action,
            target_type,
            target_id,
            json.dumps(detail or {}, ensure_ascii=False, default=str),
            datetime.utcnow(),
        )


async def create_appeal(
    user_id: str,
    session_id: str,
    question_index: int,
    reason: str,
) -> int:
    await ensure_review_tables()
    async with db_manager.get_connection() as conn:
        original_total = await conn.fetchval(
            "SELECT total FROM answer_scores WHERE session_id = $1 AND question_index = $2",
            session_id,
            question_index,
        )
        row = await conn.fetchrow(
            """
            INSERT INTO score_appeals
                (user_id, session_id, question_index, reason, status, original_total, created_at)
            VALUES ($1, $2, $3, $4, 'pending', $5, $6)
            RETURNING id
            """,
            user_id,
            session_id,
            question_index,
            reason,
            original_total,
            datetime.utcnow(),
        )
    await write_audit(user_id, "appeal_create", "score_appeal", str(row["id"]), {
        "session_id": session_id,
        "question_index": question_index,
    })
    return int(row["id"])


async def list_my_appeals(user_id: str, limit: int = 50) -> list[dict]:
    await ensure_review_tables()
    async with db_manager.get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, session_id, question_index, reason, status, original_total,
                   revised_total, admin_note, created_at, resolved_at
            FROM score_appeals
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    return [dict(r) for r in rows]


async def list_appeals(status: Optional[str] = "pending", limit: int = 100) -> list[dict]:
    await ensure_review_tables()
    async with db_manager.get_connection() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT id, user_id, session_id, question_index, reason, status,
                       original_total, revised_total, admin_note, created_at, resolved_at
                FROM score_appeals
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                status,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, user_id, session_id, question_index, reason, status,
                       original_total, revised_total, admin_note, created_at, resolved_at
                FROM score_appeals
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
    return [dict(r) for r in rows]


async def decide_appeal(
    admin_id: str,
    appeal_id: int,
    revised_total: Optional[float] = None,
    admin_note: Optional[str] = None,
    status: str = "resolved",
) -> bool:
    await ensure_review_tables()
    async with db_manager.get_connection() as conn:
        appeal = await conn.fetchrow(
            "SELECT id, session_id, question_index, original_total FROM score_appeals WHERE id = $1",
            appeal_id,
        )
        if not appeal:
            return False

        await conn.execute(
            """
            UPDATE score_appeals
            SET status = $1, revised_total = $2, admin_note = $3, resolved_at = $4
            WHERE id = $5
            """,
            status,
            revised_total,
            admin_note,
            datetime.utcnow(),
            appeal_id,
        )

        if revised_total is not None:
            await conn.execute(
                """
                UPDATE answer_scores
                SET total = $1,
                    comment = COALESCE(comment, '') || $2
                WHERE session_id = $3 AND question_index = $4
                """,
                revised_total,
                f"\n[人工复核] {admin_note or ''}".strip(),
                appeal["session_id"],
                appeal["question_index"],
            )

    await write_audit(admin_id, "appeal_decide", "score_appeal", str(appeal_id), {
        "status": status,
        "original_total": appeal["original_total"],
        "revised_total": revised_total,
        "admin_note": admin_note,
    })
    return True


async def list_audit_logs(limit: int = 200) -> list[dict]:
    await ensure_review_tables()
    async with db_manager.get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, action, target_type, target_id, detail, created_at
            FROM audit_logs
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]
