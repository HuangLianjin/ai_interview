"""账号数据闭环：导出、注销、用量统计。"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.auth import require_auth
from app.database.base import db_manager
from app.services.observability import get_usage_summary

router = APIRouter(prefix="/api/account", tags=["账号"])


def _user_id(payload: dict) -> str:
    return str(payload.get("sub", "default_user"))


@router.get("/export")
async def export_user_data(payload: dict = Depends(require_auth)):
    """导出当前用户的全部业务数据（面试会话、消息、简历、画像、评分）。"""
    user_id = _user_id(payload)
    phone = payload.get("phone", "")
    async with db_manager.get_connection() as conn:
        sessions = await conn.fetch(
            """
            SELECT session_id, title, mode, status, created_at, updated_at,
                   question_count, max_questions, job_description, company_info,
                   interview_plan, resume_filename, round_index, round_type
            FROM sessions
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        result = []
        for s in sessions:
            msgs = await conn.fetch(
                "SELECT role, content, question_index, timestamp FROM messages WHERE session_id = $1 ORDER BY timestamp ASC",
                s["session_id"],
            )
            scores = await conn.fetch(
                "SELECT question_index, question_text, answer_text, dimensions, total, comment FROM answer_scores WHERE session_id = $1 ORDER BY question_index ASC",
                s["session_id"],
            )
            item = dict(s)
            if isinstance(item.get("interview_plan"), str):
                try:
                    item["interview_plan"] = json.loads(item["interview_plan"])
                except json.JSONDecodeError:
                    item["interview_plan"] = None
            item["messages"] = [dict(m) for m in msgs]
            item["scores"] = [dict(sc) for sc in scores]
            result.append(item)

        resumes = await conn.fetch(
            "SELECT id, result_type, job_description, result_data, created_at FROM resume_results WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
        generated = await conn.fetch(
            "SELECT id, title, job_description, content, created_at FROM generated_resumes WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
        profile = await conn.fetchrow(
            "SELECT profile_data, created_at, updated_at FROM user_profile WHERE user_id = $1", user_id
        )
        usage = await get_usage_summary(user_id)

    return {
        "success": True,
        "exported_at": datetime.utcnow().isoformat(),
        "user": {"user_id": user_id, "phone": phone},
        "sessions": result,
        "resume_results": [dict(r) for r in resumes],
        "generated_resumes": [dict(g) for g in generated],
        "user_profile": dict(profile) if profile else None,
        "usage": usage,
    }


@router.delete("/delete")
async def delete_user_data(payload: dict = Depends(require_auth)):
    """删除当前用户全部数据并注销账号。"""
    user_id = _user_id(payload)
    async with db_manager.get_connection() as conn:
        await conn.execute("DELETE FROM resume_results WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM generated_resumes WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM user_profile WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM usage_logs WHERE user_id = $1", user_id)
        # messages / answer_scores 通过 sessions 外键级联删除
        await conn.execute("DELETE FROM sessions WHERE user_id = $1", user_id)
        deleted = await conn.execute("DELETE FROM users WHERE id = $1::int", int(payload["sub"]))
    return {
        "success": True,
        "message": "账号及全部数据已删除",
        "deleted_user": bool(deleted),
    }


@router.get("/usage/summary")
async def usage_summary(payload: dict = Depends(require_auth)):
    """当前用户模型请求与业务数据量统计。"""
    summary = await get_usage_summary(_user_id(payload))
    return {"success": True, "summary": summary}