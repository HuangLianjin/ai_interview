"""全链路 Trace、用户反馈与效果指标服务。

设计目标：
1. 每次面试请求记录一条 interview_runs，每个节点记录一条 interview_run_steps；
2. 记录每个节点的耗时、Token、状态和错误，方便定位卡点；
3. 记录用户反馈（评分/标签/评论），并沉淀评测失败样本形成优化池。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from app.database.base import db_manager

logger = logging.getLogger(__name__)

_tables_ready = False
_ensure_lock = asyncio.Lock()


async def ensure_trace_tables() -> None:
    """兜底建表：即使迁移没跑，也不会因为缺表让业务失败。"""
    global _tables_ready
    if _tables_ready:
        return
    async with _ensure_lock:
        if _tables_ready:
            return
        ddl = [
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
        try:
            async with db_manager.get_connection() as conn:
                for sql in ddl:
                    await conn.execute(sql)
            _tables_ready = True
        except Exception as e:  # 不让可观测性影响主流程
            logger.warning("初始化 trace 表失败: %s", e)


def _estimate_tokens(text: str) -> int:
    """粗略估算 token，用于没有 usage_metadata 的模型响应。"""
    text = text or ""
    chinese = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - chinese
    return max(1, int(chinese / 1.5 + other / 4))


def extract_usage(output: Any, input_text: str = "", output_text: str = "") -> tuple[int, int]:
    """从 LangChain 输出里尽可能取到 token 用量，取不到就估算。"""
    usage = getattr(output, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        usage = {}
    prompt_tokens = (
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or usage.get("input_token_count")
        or 0
    )
    completion_tokens = (
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or usage.get("output_token_count")
        or 0
    )
    if not prompt_tokens and input_text:
        prompt_tokens = _estimate_tokens(input_text)
    if not completion_tokens and output_text:
        completion_tokens = _estimate_tokens(output_text)
    return int(prompt_tokens or 0), int(completion_tokens or 0)


class TraceRecorder:
    """一次面试请求的全链路记录器。"""

    def __init__(self, session_id: str, user_id: str = "", entrypoint: str = "unknown"):
        self.run_id = uuid.uuid4().hex
        self.session_id = session_id or ""
        self.user_id = user_id or ""
        self.entrypoint = entrypoint
        self._started = time.perf_counter()
        self._last = self._started
        self.prompt_tokens = 0
        self.completion_tokens = 0

    async def start(self) -> str:
        await ensure_trace_tables()
        try:
            async with db_manager.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO interview_runs
                        (run_id, session_id, user_id, entrypoint, status, started_at)
                    VALUES ($1, $2, $3, $4, 'running', $5)
                    """,
                    self.run_id,
                    self.session_id,
                    self.user_id,
                    self.entrypoint,
                    datetime.utcnow(),
                )
        except Exception as e:
            logger.warning("记录 trace run 失败: %s", e)
        return self.run_id

    async def record_step(
        self,
        node_name: str,
        status: str = "success",
        model: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        detail: Optional[dict] = None,
        error: Optional[str] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        now = time.perf_counter()
        if latency_ms is None:
            latency_ms = (now - self._last) * 1000
        self._last = now
        self.prompt_tokens += int(prompt_tokens or 0)
        self.completion_tokens += int(completion_tokens or 0)
        await ensure_trace_tables()
        try:
            async with db_manager.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO interview_run_steps
                        (run_id, session_id, node_name, model, status, latency_ms,
                         prompt_tokens, completion_tokens, detail, error, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                    self.run_id,
                    self.session_id,
                    node_name,
                    model,
                    status,
                    float(latency_ms or 0),
                    int(prompt_tokens or 0),
                    int(completion_tokens or 0),
                    json.dumps(detail or {}, ensure_ascii=False, default=str),
                    error,
                    datetime.utcnow(),
                )
        except Exception as e:
            logger.warning("记录 trace step 失败: %s", e)

    async def record_llm_event(self, event: dict) -> None:
        """从 LangChain on_chat_model_end 事件记录模型用量。"""
        try:
            data = event.get("data") or {}
            output = data.get("output")
            content = getattr(output, "content", "") or ""
            model = (event.get("metadata") or {}).get("ls_model_name") or None
            prompt_tokens, completion_tokens = extract_usage(output, output_text=str(content))
            node_name = (event.get("metadata") or {}).get("langgraph_node") or "llm"
            await self.record_step(
                node_name=f"{node_name}:llm",
                status="success",
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except Exception as e:
            logger.debug("记录 LLM 用量失败: %s", e)

    async def finish(self, status: str = "success", error: Optional[str] = None) -> None:
        total_ms = (time.perf_counter() - self._started) * 1000
        await ensure_trace_tables()
        try:
            async with db_manager.get_connection() as conn:
                await conn.execute(
                    """
                    UPDATE interview_runs
                    SET status = $1, total_latency_ms = $2, prompt_tokens = $3,
                        completion_tokens = $4, error = $5, finished_at = $6
                    WHERE run_id = $7
                    """,
                    status,
                    float(total_ms),
                    self.prompt_tokens,
                    self.completion_tokens,
                    error,
                    datetime.utcnow(),
                    self.run_id,
                )
        except Exception as e:
            logger.warning("结束 trace run 失败: %s", e)


async def record_step(
    session_id: str,
    node_name: str,
    status: str = "success",
    model: Optional[str] = None,
    latency_ms: float = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    detail: Optional[dict] = None,
    error: Optional[str] = None,
    run_id: Optional[str] = None,
) -> None:
    """记录一个独立节点（评分、画像、报告等非 SSE 流程）。"""
    await ensure_trace_tables()
    try:
        async with db_manager.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO interview_run_steps
                    (run_id, session_id, node_name, model, status, latency_ms,
                     prompt_tokens, completion_tokens, detail, error, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                run_id or f"step-{uuid.uuid4().hex}",
                session_id,
                node_name,
                model,
                status,
                float(latency_ms or 0),
                int(prompt_tokens or 0),
                int(completion_tokens or 0),
                json.dumps(detail or {}, ensure_ascii=False, default=str),
                error,
                datetime.utcnow(),
            )
    except Exception as e:
        logger.warning("记录独立 step 失败: %s", e)


async def list_runs(session_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    await ensure_trace_tables()
    async with db_manager.get_connection() as conn:
        if session_id:
            rows = await conn.fetch(
                """
                SELECT run_id, session_id, user_id, entrypoint, status, total_latency_ms,
                       prompt_tokens, completion_tokens, error, started_at, finished_at
                FROM interview_runs
                WHERE session_id = $1
                ORDER BY started_at DESC
                LIMIT $2
                """,
                session_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT run_id, session_id, user_id, entrypoint, status, total_latency_ms,
                       prompt_tokens, completion_tokens, error, started_at, finished_at
                FROM interview_runs
                ORDER BY started_at DESC
                LIMIT $1
                """,
                limit,
            )
    return [dict(r) for r in rows]


async def get_run_detail(run_id: str) -> Optional[dict]:
    await ensure_trace_tables()
    async with db_manager.get_connection() as conn:
        run = await conn.fetchrow(
            "SELECT * FROM interview_runs WHERE run_id = $1",
            run_id,
        )
        if not run:
            return None
        steps = await conn.fetch(
            """
            SELECT node_name, model, status, latency_ms, prompt_tokens, completion_tokens,
                   detail, error, created_at
            FROM interview_run_steps
            WHERE run_id = $1
            ORDER BY created_at ASC
            """,
            run_id,
        )
    result = dict(run)
    result["steps"] = [dict(s) for s in steps]
    return result


async def get_trace_summary(days: int = 7) -> dict:
    await ensure_trace_tables()
    since = datetime.utcnow() - timedelta(days=max(1, days))
    async with db_manager.get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT status, total_latency_ms, prompt_tokens, completion_tokens
            FROM interview_runs
            WHERE started_at >= $1
            """,
            since,
        )
        node_rows = await conn.fetch(
            """
            SELECT node_name, status, AVG(latency_ms) AS avg_latency_ms,
                   COUNT(*) AS calls, SUM(prompt_tokens + completion_tokens) AS tokens
            FROM interview_run_steps
            WHERE created_at >= $1
            GROUP BY node_name, status
            ORDER BY calls DESC
            """,
            since,
        )
    total = len(rows)
    success = sum(1 for r in rows if r["status"] == "success")
    latencies = sorted(float(r["total_latency_ms"] or 0) for r in rows)
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0
    tokens = sum(int(r["prompt_tokens"] or 0) + int(r["completion_tokens"] or 0) for r in rows)
    return {
        "days": days,
        "total_runs": total,
        "success_runs": success,
        "success_rate": round(success / total, 4) if total else 0.0,
        "error_runs": total - success,
        "avg_latency_ms": round(sum(latencies) / total, 1) if total else 0.0,
        "p95_latency_ms": round(p95, 1),
        "total_tokens": tokens,
        "nodes": [dict(r) for r in node_rows],
    }


async def save_feedback(
    user_id: str,
    target_type: str,
    target_id: Optional[str] = None,
    session_id: Optional[str] = None,
    rating: Optional[int] = None,
    tags: Optional[list] = None,
    comment: Optional[str] = None,
) -> int:
    await ensure_trace_tables()
    async with db_manager.get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_feedback
                (user_id, session_id, target_type, target_id, rating, tags, comment, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            user_id or "anonymous",
            session_id,
            target_type,
            target_id,
            rating,
            json.dumps(tags or [], ensure_ascii=False),
            comment,
            datetime.utcnow(),
        )
    return int(row["id"])


async def list_feedback(
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    await ensure_trace_tables()
    conditions = []
    params: list[Any] = []
    if user_id:
        params.append(user_id)
        conditions.append(f"user_id = ${len(params)}")
    if target_type:
        params.append(target_type)
        conditions.append(f"target_type = ${len(params)}")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    async with db_manager.get_connection() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, user_id, session_id, target_type, target_id, rating, tags, comment, created_at
            FROM user_feedback
            {where}
            ORDER BY created_at DESC
            LIMIT ${len(params)}
            """,
            *params,
        )
    return [dict(r) for r in rows]


async def get_product_metrics(days: int = 7) -> dict:
    """用户真实使用与效果指标：完成率、反馈评分、产出量等。"""
    await ensure_trace_tables()
    since = datetime.utcnow() - timedelta(days=max(1, days))
    async with db_manager.get_connection() as conn:
        session_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'completed') AS completed
            FROM sessions
            WHERE created_at >= $1
            """,
            since,
        )
        message_count = await conn.fetchval(
            "SELECT COUNT(*) FROM messages WHERE timestamp >= $1",
            since,
        )
        resume_count = await conn.fetchval(
            "SELECT COUNT(*) FROM resume_results WHERE created_at >= $1",
            since,
        )
        generated_count = await conn.fetchval(
            "SELECT COUNT(*) FROM generated_resumes WHERE created_at >= $1",
            since,
        )
        feedback_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS total,
                   COALESCE(AVG(rating), 0) AS avg_rating,
                   COUNT(*) FILTER (WHERE rating <= 2) AS low_rating
            FROM user_feedback
            WHERE created_at >= $1
            """,
            since,
        )
        open_failures = await conn.fetchval(
            "SELECT COUNT(*) FROM eval_failures WHERE status = 'open'"
        )
    total_sessions = int(session_row["total"] or 0)
    completed_sessions = int(session_row["completed"] or 0)
    return {
        "days": days,
        "sessions_total": total_sessions,
        "sessions_completed": completed_sessions,
        "completion_rate": round(completed_sessions / total_sessions, 4) if total_sessions else 0.0,
        "messages": int(message_count or 0),
        "resume_results": int(resume_count or 0),
        "generated_resumes": int(generated_count or 0),
        "feedback_total": int(feedback_row["total"] or 0),
        "feedback_avg_rating": round(float(feedback_row["avg_rating"] or 0), 2),
        "feedback_low_rating": int(feedback_row["low_rating"] or 0),
        "open_eval_failures": int(open_failures or 0),
    }


async def save_eval_failure(
    case_id: str,
    category: str,
    question: str,
    answer: str,
    expected: Optional[dict] = None,
    actual: Optional[dict] = None,
) -> None:
    await ensure_trace_tables()
    async with db_manager.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO eval_failures
                (case_id, category, question, answer, expected, actual, status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, 'open', $7)
            """,
            case_id,
            category,
            question,
            answer,
            json.dumps(expected or {}, ensure_ascii=False),
            json.dumps(actual or {}, ensure_ascii=False),
            datetime.utcnow(),
        )


async def list_eval_failures(status: Optional[str] = "open", limit: int = 200) -> list[dict]:
    await ensure_trace_tables()
    async with db_manager.get_connection() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT id, case_id, category, question, answer, expected, actual, status, created_at
                FROM eval_failures
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
                SELECT id, case_id, category, question, answer, expected, actual, status, created_at
                FROM eval_failures
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
    return [dict(r) for r in rows]


async def resolve_eval_failure(failure_id: int, status: str = "resolved") -> bool:
    await ensure_trace_tables()
    async with db_manager.get_connection() as conn:
        result = await conn.execute(
            "UPDATE eval_failures SET status = $1 WHERE id = $2",
            status,
            failure_id,
        )
    return result.endswith("1")
