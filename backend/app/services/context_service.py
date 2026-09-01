"""多轮对话上下文管理：Token 估算、历史压缩、预算控制。"""
import math
from typing import List, Dict, Any


def estimate_tokens(text: str) -> int:
    """中文按约 1.5 字/token、英文按 4 字符/token 粗略估算。"""
    text = text or ""
    chinese_chars = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other_chars = len(text) - chinese_chars
    return max(1, math.ceil(chinese_chars / 1.5 + other_chars / 4))


def compress_messages(
    messages: List[Dict[str, Any]],
    max_tokens: int = 6000,
    keep_last: int = 12,
) -> List[Dict[str, Any]]:
    """按 Token 预算压缩历史：优先保留最近消息，超预算时裁剪最旧内容。"""
    if not messages:
        return []

    recent = messages[-keep_last:]
    used = sum(estimate_tokens(m.get("content", "")) for m in recent)
    if used <= max_tokens:
        return recent

    compressed = []
    budget = max_tokens
    for m in reversed(recent):
        content = m.get("content", "")
        tokens = estimate_tokens(content)
        if tokens > budget and compressed:
            content = content[: max(200, budget * 3)]
            tokens = estimate_tokens(content)
        if tokens > budget and not compressed:
            content = content[: max(200, budget * 3)]
            tokens = estimate_tokens(content)
        compressed.append({**m, "content": content})
        budget -= tokens
        if budget <= 0:
            break
    return list(reversed(compressed))


def trim_history(history: List[Dict[str, Any]], max_chars: int = 12000, keep_pairs: int = 8) -> List[Dict[str, Any]]:
    """压缩问答历史，保留最近 keep_pairs 轮问答并限制总字符数。"""
    pairs = history[-keep_pairs:]
    total = sum(len(p.get("question", "")) + len(p.get("answer", "")) for p in pairs)
    if total <= max_chars:
        return pairs
    result = []
    used = 0
    for p in reversed(pairs):
        q = p.get("question", "")
        a = p.get("answer", "")
        if used + len(q) + len(a) > max_chars:
            remain = max_chars - used
            if remain > 200:
                a = a[: remain - min(len(q), 200)]
                result.append({"question": q[:200], "answer": a})
            break
        result.append(p)
        used += len(q) + len(a)
    return list(reversed(result))