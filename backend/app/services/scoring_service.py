"""每题作答评分服务。

每道题回答后调用 Smart LLM 从技术、表达、深度三个维度评分，
结果持久化到 answer_scores，供面评报告和前端展示使用。
"""
import json
import logging
import re
from datetime import datetime
from typing import Optional

from app.core.llms import get_llm_for_request
from app.database.base import db_manager

logger = logging.getLogger(__name__)


SCORE_PROMPT = """你是一位严格的技术面试官。请针对候选人对单道面试题的回答进行评分。

【面试问题】：
{question}

【候选人回答】：
{answer}

【评分要求】：
从以下 3 个维度评分（0-10 分，允许一位小数）：
1. tech：技术正确性与深度
2. expression：表达清晰度与结构化程度
3. depth：思考深度与细节支撑

请直接输出纯 JSON（不要 markdown 代码块），格式如下：
{{
  "dimensions": {{
    "tech": 7.5,
    "expression": 8.0,
    "depth": 6.5
  }},
  "total": 7.3,
  "comment": "一句话点评，指出亮点和不足"
}}
"""


def _parse_score_response(text: str) -> Optional[dict]:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None


async def score_answer(
    session_id: str,
    question_index: int,
    question_text: str,
    answer_text: str,
    api_config: Optional[dict] = None,
) -> Optional[dict]:
    """对单题作答评分并保存。"""
    if not question_text or not answer_text:
        return None

    try:
        llm = get_llm_for_request(api_config, channel="smart")
        prompt = SCORE_PROMPT.format(question=question_text, answer=answer_text[:4000])
        response = await llm.ainvoke(prompt)
        data = _parse_score_response(response.content)
        if not data:
            logger.warning(f"[Scoring] 解析评分 JSON 失败: session={session_id} q={question_index}")
            return None

        dimensions = data.get("dimensions") or {}
        dimensions["strengths"] = data.get("strengths") or []
        dimensions["weaknesses"] = data.get("weaknesses") or []
        dimensions["suggestions"] = data.get("suggestions") or []
        total = float(data.get("total") or 0)
        comment = (data.get("comment") or "").strip()
        now = datetime.utcnow()

        async with db_manager.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO answer_scores
                    (session_id, question_index, question_text, answer_text, dimensions, total, comment, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (session_id, question_index)
                DO UPDATE SET
                    question_text = EXCLUDED.question_text,
                    answer_text = EXCLUDED.answer_text,
                    dimensions = EXCLUDED.dimensions,
                    total = EXCLUDED.total,
                    comment = EXCLUDED.comment,
                    created_at = EXCLUDED.created_at
                """,
                session_id, question_index, question_text, answer_text,
                json.dumps(dimensions), total, comment, now,
            )
        logger.info(f"[Scoring] 已保存评分: session={session_id} q={question_index} total={total}")
        return {"dimensions": dimensions, "total": total, "comment": comment}
    except Exception as e:
        logger.error(f"[Scoring] 评分失败: {e}")
        return None


async def get_session_scores(session_id: str) -> list[dict]:
    """获取会话内所有作答评分。"""
    async with db_manager.get_connection() as conn:
        rows = await conn.fetch(
            "SELECT question_index, question_text, answer_text, dimensions, total, comment "
            "FROM answer_scores WHERE session_id = $1 ORDER BY question_index ASC",
            session_id,
        )
    result = []
    for r in rows:
        item = dict(r)
        if isinstance(item.get("dimensions"), str):
            try:
                item["dimensions"] = json.loads(item["dimensions"])
            except (json.JSONDecodeError, TypeError):
                item["dimensions"] = {}
        result.append(item)
    return result