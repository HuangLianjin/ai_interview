"""轻量 RAG 检索服务。

用字符 n-gram 哈希生成稠密向量并做余弦相似度召回，
不需要额外 Embedding API，后续可无缝替换为 PGVector + 在线 Embedding。
"""
import math
import re
from collections import Counter

from app.database.base import db_manager

VECTOR_DIM = 256
_NGRAM = 3


def _hash_token(token: str) -> int:
    h = 2166136261
    for ch in token:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def embed_text(text: str) -> list[float]:
    text = (text or "").lower()
    tokens = re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text)
    grams = []
    for token in tokens:
        if len(token) <= 1:
            grams.append(token)
        else:
            grams.append(token)
            for i in range(len(token) - _NGRAM + 1):
                grams.append(token[i:i + _NGRAM])
    counter = Counter(grams)
    vec = [0.0] * VECTOR_DIM
    for gram, freq in counter.items():
        idx = _hash_token(gram) % VECTOR_DIM
        vec[idx] += 1.0 + math.log(freq)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


async def retrieve_knowledge(query: str, top_k: int = 4) -> list[dict]:
    """按相似度召回知识库条目。"""
    async with db_manager.get_connection() as conn:
        rows = await conn.fetch(
            "SELECT id, topic, title, content FROM knowledge_chunks"
        )
    query_vec = embed_text(query)
    scored = []
    for r in rows:
        text = f"{r['topic']} {r['title']} {r['content']}"
        score = _cosine(query_vec, embed_text(text))
        scored.append({"id": r["id"], "topic": r["topic"], "title": r["title"], "content": r["content"], "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def format_knowledge(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    lines = ["【检索到的参考资料（用于出题参考）】"]
    for i, c in enumerate(chunks, 1):
        lines.append(f"{i}. [{c['title']}] {c['content']}")
    return "\n".join(lines)