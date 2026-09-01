"""统一可观测性：结构化请求日志、模型用量统计。"""
import json
import logging
from datetime import datetime
from typing import Optional

from app.database.base import db_manager

logger = logging.getLogger(__name__)


def log_json(event: str, **fields):
    """输出一行结构化 JSON 日志，便于后续接入日志平台。"""
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


async def record_request(
    user_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    extra: Optional[dict] = None,
):
    """记录一次 HTTP 请求到 usage_logs。"""
    try:
        async with db_manager.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO usage_logs
                    (user_id, method, path, status_code, duration_ms, extra, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                user_id or "anonymous",
                method,
                path,
                status_code,
                duration_ms,
                json.dumps(extra or {}, ensure_ascii=False),
                datetime.utcnow(),
            )
    except Exception as e:
        logger.warning("记录请求日志失败: %s", e)


async def get_usage_summary(user_id: str) -> dict:
    """按用户汇总请求量、耗时、错误数与业务数据量。"""
    async with db_manager.get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS request_count,
                COALESCE(SUM(duration_ms), 0) AS total_duration_ms,
                COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
                COUNT(*) FILTER (WHERE status_code >= 500) AS error_count
            FROM usage_logs
            WHERE user_id = $1
            """,
            user_id,
        )
        session_count = await conn.fetchval(
            "SELECT COUNT(*) FROM sessions WHERE user_id = $1", user_id
        )
        message_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM messages
            WHERE session_id IN (SELECT session_id FROM sessions WHERE user_id = $1)
            """,
            user_id,
        )
        resume_count = await conn.fetchval(
            "SELECT COUNT(*) FROM resume_results WHERE user_id = $1", user_id
        )
        generated_count = await conn.fetchval(
            "SELECT COUNT(*) FROM generated_resumes WHERE user_id = $1", user_id
        )
        profile_count = await conn.fetchval(
            "SELECT COUNT(*) FROM user_profile WHERE user_id = $1", user_id
        )

    return {
        "request_count": row["request_count"],
        "total_duration_ms": round(float(row["total_duration_ms"]), 1),
        "avg_duration_ms": round(float(row["avg_duration_ms"]), 1),
        "error_count": row["error_count"],
        "session_count": session_count,
        "message_count": message_count,
        "resume_count": resume_count,
        "generated_resume_count": generated_count,
        "profile_count": profile_count,
    }