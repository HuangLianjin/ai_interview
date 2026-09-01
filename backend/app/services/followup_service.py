"""智能追问服务：判断回答深度，决定继续追问还是进入下一题。"""
import json
import logging
import re
from typing import Optional

from app.core.llms import get_async_chat_client

logger = logging.getLogger(__name__)

FOLLOWUP_PROMPT = """你是一位严格且敏锐的技术面试官。请判断候选人的回答是否值得继续追问。

【当前问题】：
{question}

【候选人回答】：
{answer}

【之前的问答历史】：
{history}

【已追问次数】：{followups_so_far}

【判断规则】：
- 如果回答比较浅、泛泛而谈、只说概念没有细节，且追问次数未达到上限，则应该继续追问。
- 追问要基于候选人原话中的具体点，指出矛盾或让候选人展开细节，不要问新的大题。
- 如果回答已经比较深入、有细节和思考，或追问次数已达上限，则进入下一题。

【输出格式】：只输出纯 JSON，不要 markdown 代码块：
{{
  "action": "followup" 或 "next",
  "followup_question": "追问内容（action=followup 时必填）",
  "acknowledgment": "一句自然的过渡语，如：嗯，我理解了。",
  "reason": "判断原因"
}}
"""


def _parse(text: str) -> Optional[dict]:
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


async def decide_followup(
    question: str,
    answer: str,
    history: list[dict],
    followups_so_far: int,
    api_config: Optional[dict] = None,
    max_follow_ups: int = 2,
) -> dict:
    try:
        client, model = get_async_chat_client(api_config, channel="smart")
        history_text = "\n".join(
            f"Q: {h.get('question', '')}\nA: {h.get('answer', '')[:300]}"
            for h in history[-3:]
        ) or "（暂无）"
        prompt = FOLLOWUP_PROMPT.format(
            question=question,
            answer=answer[:3000],
            history=history_text,
            followups_so_far=followups_so_far,
        )
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        data = _parse(resp.choices[0].message.content or "") or {}
        fq = (data.get("followup_question") or "").strip()
        # 部分模型会把整个 JSON 再包一层字符串，这里做清洗
        if fq.startswith("{"):
            try:
                inner = json.loads(fq)
                fq = (inner.get("followup_question") or inner.get("question") or fq).strip()
            except json.JSONDecodeError:
                pass
        ack = (data.get("acknowledgment") or "嗯，我了解了。").strip()
        if ack.startswith("{"):
            try:
                inner_ack = json.loads(ack)
                ack = (inner_ack.get("acknowledgment") or "嗯，我了解了。").strip()
            except json.JSONDecodeError:
                pass
        action = data.get("action")
        if action not in ("followup", "next"):
            action = "next"
        return {
            "action": action,
            "followup_question": fq,
            "acknowledgment": ack,
            "reason": (data.get("reason") or "").strip(),
        }
    except Exception as e:
        logger.warning(f"[FollowUp] 追问决策失败，默认进入下一题: {e}")
        return {"action": "next", "followup_question": "", "acknowledgment": "嗯，我了解了。", "reason": "fallback"}
