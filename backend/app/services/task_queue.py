"""数据库任务队列：替代进程内 asyncio.create_task，服务重启不丢任务。

适用于没有 Redis 的部署环境；后续可平滑替换成 Celery/RQ/Arq。
"""
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


async def ensure_task_table() -> None:
    global _tables_ready
    if _tables_ready:
        return
    async with _lock:
        if _tables_ready:
            return
        try:
            async with db_manager.get_connection() as conn:
                await conn.execute(
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
                    """
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_background_tasks_status ON background_tasks(status, created_at ASC)"
                )
            _tables_ready = True
        except Exception as e:
            logger.warning("初始化任务队列表失败: %s", e)


async def enqueue_task(task_type: str, payload: Optional[dict] = None, max_attempts: int = 3) -> int:
    await ensure_task_table()
    async with db_manager.get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO background_tasks (task_type, payload, status, max_attempts, created_at)
            VALUES ($1, $2, 'pending', $3, $4)
            RETURNING id
            """,
            task_type,
            json.dumps(payload or {}, ensure_ascii=False, default=str),
            max_attempts,
            datetime.utcnow(),
        )
    return int(row["id"])


async def claim_task() -> Optional[dict]:
    """用 FOR UPDATE SKIP LOCKED 抢占一个待执行任务，支持多 worker。"""
    await ensure_task_table()
    async with db_manager.get_connection() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, task_type, payload, attempts, max_attempts
                FROM background_tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
            if not row:
                return None
            await conn.execute(
                """
                UPDATE background_tasks
                SET status = 'running', attempts = attempts + 1, started_at = $1
                WHERE id = $2
                """,
                datetime.utcnow(),
                row["id"],
            )
    task = dict(row)
    if isinstance(task.get("payload"), str):
        try:
            task["payload"] = json.loads(task["payload"])
        except json.JSONDecodeError:
            task["payload"] = {}
    return task


async def complete_task(task_id: int) -> None:
    await ensure_task_table()
    async with db_manager.get_connection() as conn:
        await conn.execute(
            """
            UPDATE background_tasks
            SET status = 'done', finished_at = $1, error = NULL
            WHERE id = $2
            """,
            datetime.utcnow(),
            task_id,
        )


async def fail_task(task_id: int, error: str) -> None:
    """失败任务在未超过最大次数时回到 pending，否则标记 failed。"""
    await ensure_task_table()
    async with db_manager.get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT attempts, max_attempts FROM background_tasks WHERE id = $1",
            task_id,
        )
        if not row:
            return
        can_retry = int(row["attempts"] or 0) < int(row["max_attempts"] or 3)
        await conn.execute(
            """
            UPDATE background_tasks
            SET status = $1, error = $2, finished_at = $3
            WHERE id = $4
            """,
            "pending" if can_retry else "failed",
            error,
            None if can_retry else datetime.utcnow(),
            task_id,
        )


async def task_stats() -> dict:
    await ensure_task_table()
    async with db_manager.get_connection() as conn:
        rows = await conn.fetch(
            "SELECT status, COUNT(*) AS n FROM background_tasks GROUP BY status"
        )
    return {row["status"]: int(row["n"]) for row in rows}
