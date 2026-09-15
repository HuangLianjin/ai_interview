"""Agent 工具层：把可复用能力封装成带 schema 的工具。

当前提供三个工具：
1. job_skill_lookup：从 JD 中提取岗位技能与考察点
2. company_info_lookup：给出目标公司的面试关注点
3. question_bank_lookup：按主题检索题库/知识点并生成候选问题

设计上预留了 MCP 适配空间：工具通过统一 registry 注册，name/description/parameters
可以直接映射成 MCP tool schema。
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable, Optional

from app.services.knowledge_base import CHUNKS
from app.services.trace_service import record_step

logger = logging.getLogger(__name__)


async def _job_skill_lookup(params: dict) -> dict:
    jd = str(params.get("job_description") or "")
    matched = []
    for topic, title, content in CHUNKS:
        if topic.lower() in jd.lower() or title[:4] in jd:
            matched.append({"topic": topic, "title": title, "content": content})

    skills = []
    for item in matched:
        skills.append(item["title"])

    # 常见技术关键词兜底
    keyword_map = {
        "python": "Python", "java": "Java", "fastapi": "FastAPI", "spring": "Spring Boot",
        "postgresql": "PostgreSQL", "mysql": "MySQL", "redis": "Redis", "docker": "Docker",
        "kubernetes": "Kubernetes", "langchain": "LangChain", "langgraph": "LangGraph",
        "rag": "RAG", "agent": "Agent", "llm": "大模型应用", "sse": "SSE",
        "jwt": "JWT", "nginx": "Nginx", "微服务": "微服务", "高并发": "高并发",
    }
    for key, label in keyword_map.items():
        if key.lower() in jd.lower() and label not in skills:
            skills.append(label)

    return {
        "skills": skills[:20],
        "matched_knowledge": matched[:10],
        "suggestion": "优先围绕上述技能准备项目案例、原理和踩坑经验。",
    }


async def _company_info_lookup(params: dict) -> dict:
    company = str(params.get("company_name") or "").strip()
    # 不做外部公司数据抓取，给出结构化准备框架，避免编造公司事实
    return {
        "company": company or "未知公司",
        "focus_points": [
            "公司主营业务与目标岗位的业务关系",
            "岗位 JD 中的硬性技术要求和加分项",
            "团队技术栈与项目复杂度",
            "候选人能提供的可迁移经验",
        ],
        "reminder": "公司具体业务数据需要用户自行核实，本工具不编造公司事实。",
    }


async def _question_bank_lookup(params: dict) -> dict:
    topic = str(params.get("topic") or "").strip().lower()
    limit = int(params.get("limit") or 5)
    matched = []
    for t, title, content in CHUNKS:
        if not topic or topic in t.lower() or topic in title.lower() or topic in content.lower():
            matched.append({"topic": t, "title": title, "content": content})
    matched = matched[:max(1, min(limit, 10))]

    questions = []
    for item in matched:
        questions.append(f"请解释 {item['title']} 的核心机制和常见坑。")
        questions.append(f"你在项目里如何使用 {item['title']}？遇到过什么问题？")
        questions.append(f"如果线上出现与 {item['title']} 相关的问题，你会怎么排查？")

    return {
        "topic": topic or "通用",
        "knowledge_points": matched,
        "candidate_questions": questions[: max(1, limit) * 2],
    }


TOOLS: dict[str, dict[str, Any]] = {
    "job_skill_lookup": {
        "description": "从岗位 JD 中提取技能要求与考察点",
        "parameters": {
            "type": "object",
            "properties": {"job_description": {"type": "string", "description": "岗位 JD 文本"}},
            "required": ["job_description"],
        },
        "handler": _job_skill_lookup,
    },
    "company_info_lookup": {
        "description": "生成目标公司的面试准备关注点（不编造公司事实）",
        "parameters": {
            "type": "object",
            "properties": {"company_name": {"type": "string", "description": "公司名称"}},
            "required": ["company_name"],
        },
        "handler": _company_info_lookup,
    },
    "question_bank_lookup": {
        "description": "按主题检索知识点并生成候选面试问题",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "技术主题，如 redis、langgraph"},
                "limit": {"type": "integer", "description": "返回条数", "default": 5},
            },
            "required": ["topic"],
        },
        "handler": _question_bank_lookup,
    },
}


def list_tools() -> list[dict]:
    return [
        {
            "name": name,
            "description": spec["description"],
            "parameters": spec["parameters"],
        }
        for name, spec in TOOLS.items()
    ]


async def invoke_tool(name: str, params: Optional[dict] = None, session_id: Optional[str] = None) -> dict:
    """调用工具并记录 Trace；工具失败会返回结构化错误而不是抛出。"""
    spec = TOOLS.get(name)
    if not spec:
        return {"success": False, "error": f"未知工具: {name}"}

    handler: Callable[[dict], Any] = spec["handler"]
    started = time.perf_counter()
    try:
        result = await handler(params or {})
        await record_step(
            session_id=session_id or f"tool:{name}",
            node_name=f"tool:{name}",
            status="success",
            latency_ms=(time.perf_counter() - started) * 1000,
            detail={"params_keys": list((params or {}).keys())},
        )
        return {"success": True, "tool": name, "result": result}
    except Exception as e:
        logger.warning("工具 %s 调用失败: %s", name, e)
        await record_step(
            session_id=session_id or f"tool:{name}",
            node_name=f"tool:{name}",
            status="error",
            latency_ms=(time.perf_counter() - started) * 1000,
            error=str(e),
        )
        return {"success": False, "tool": name, "error": str(e)}
