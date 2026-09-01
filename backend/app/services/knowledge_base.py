"""内置技术知识库：出题时用于 RAG 检索增强。"""
from datetime import datetime

from app.database.base import db_manager

CHUNKS = [
    ("python", "Python 语言特性", "Python 是动态类型解释型语言，GIL 限制多线程 CPU 并行；常用异步 asyncio 处理 IO 密集任务。面试常问：可变/不可变对象、装饰器、生成器、GIL、垃圾回收、上下文管理器。"),
    ("fastapi", "FastAPI 核心机制", "FastAPI 基于 Starlette 和 Pydantic，支持自动请求校验、OpenAPI 文档、依赖注入和异步路由。生产部署常用 Uvicorn/Gunicorn，注意同步阻塞操作会卡住事件循环。"),
    ("postgresql", "PostgreSQL 事务与索引", "PostgreSQL 默认 READ COMMITTED，支持 MVCC、JSONB、GIN/BTree 索引、CTE、窗口函数和行级锁。面试常问：事务隔离级别、索引失效场景、慢查询排查、连接池。"),
    ("sqlalchemy", "SQLAlchemy ORM 与连接池", "SQLAlchemy 通过 Session 管理事务，连接池复用数据库连接；N+1 查询通常用 selectinload/joinedload 解决。生产环境建议配置 pool_pre_ping 避免连接失效。"),
    ("langgraph", "LangGraph 状态机与多智能体", "LangGraph 用 StateGraph 定义节点和有向边，节点返回状态增量，checkpointer 保存断点。适合工作流/多智能体编排，支持人工中断、条件路由和持久化恢复。"),
    ("langchain", "LangChain 抽象层", "LangChain 提供 ChatModel、PromptTemplate、Tool、Retriever 抽象；LangChain Core 是模型无关核心。面试常问：LCEL、工具调用、回调、缓存。"),
    ("rag", "RAG 检索增强生成", "RAG 流程：文档切块 -> 向量化 -> 向量库召回 -> 重排序 -> 注入 Prompt。关键点：chunk 大小、Embedding 模型、混合检索（BM25+向量）、引用溯源、幻觉控制。"),
    ("agent", "Agent 与工具调用", "Agent 核心循环：观察 -> 推理 -> 行动 -> 观察结果；通过 Function Calling 或 MCP 调用外部工具。常见坑：工具参数校验、超时重试、循环上限、状态隔离。"),
    ("sse", "SSE 流式输出", "SSE 基于 HTTP 长连接，服务端按 text/event-stream 推送；nginx 需要关闭 proxy_buffering。相比 WebSocket，SSE 单向推送更简单，适合 LLM token 流。"),
    ("jwt", "JWT 认证机制", "JWT 由 Header.Payload.Signature 组成，服务端用密钥验签；无状态但有吊销难题。生产注意：过期时间、密钥管理、敏感信息不入 Payload、刷新令牌策略。"),
    ("redis", "Redis 缓存与并发", "Redis 单线程模型，常用 String/Hash/List/Set/ZSet；缓存穿透、击穿、雪崩是高频考点；分布式锁用 SETNX+过期时间+Lua 释放。"),
    ("docker", "Docker 容器化部署", "Dockerfile 多阶段构建可减小镜像；docker-compose 编排多服务；生产注意健康检查、日志卷、资源限制、镜像漏洞扫描。"),
    ("nginx", "Nginx 反向代理", "Nginx 处理静态资源和高并发转发；location 匹配、proxy_pass、upstream 负载均衡、WebSocket/SSE 代理配置是高频考点。"),
    ("llm", "大模型应用评估", "LLM 应用评估：输出质量、延迟、成本、失败率；常用指标有准确率、召回率、人工抽检、LLM-as-Judge；Prompt 版本管理很重要。"),
    ("system_design", "系统设计通用方法", "先明确需求和数据量，再设计 API、数据模型、存储、缓存、消息队列；面试关注：读写比、QPS、扩展性、可用性、一致性权衡。"),
    ("voice", "语音面试技术栈", "语音链路：录音 -> ASR 转写 -> LLM 生成 -> TTS 合成；ASR 常用 Whisper，TTS 可用 Edge TTS/火山；端到端延迟优化靠流式处理和缓存。"),
    ("sql", "SQL 查询优化", "慢查询先看 EXPLAIN ANALYZE；避免 SELECT *、隐式类型转换、函数包裹索引列；分页深偏移可用游标/延迟关联。"),
    ("websocket", "WebSocket 与实时通信", "WebSocket 全双工长连接，适合实时交互；心跳保活、断线重连、消息顺序和幂等是生产要点。"),
    ("testing", "后端测试策略", "单元测试测纯逻辑，接口测试测 HTTP 契约，集成测试连真实数据库；LLM 调用用 mock 保证稳定；CI 中跑测试和构建。"),
    ("security", "API 安全", "认证用 JWT/OAuth，校验用 Pydantic；防注入、限流、CORS、日志脱敏、敏感信息不入前端。"),
    ("memory", "多轮对话记忆", "短期记忆放会话状态，长期记忆存数据库；LangGraph checkpointer 持久化状态；上下文过长时做摘要压缩或裁剪。"),
    ("evaluation", "Agent 结果评估", "评估 Agent：任务完成率、工具调用成功率、中间步骤正确性、终态质量；用固定测试集 + LLM-as-Judge 自动化回归。"),
    ("deployment", "上线部署流程", "构建镜像 -> 迁移数据库 -> 启动服务 -> 健康检查 -> 灰度/回滚；上线前准备 .env、日志、监控告警和备份。"),
]


async def ensure_knowledge_base() -> None:
    """启动时写入知识库（仅当表为空）。"""
    async with db_manager.get_connection() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_chunks")
        if count and count > 0:
            return
        now = datetime.utcnow()
        for topic, title, content in CHUNKS:
            await conn.execute(
                "INSERT INTO knowledge_chunks (topic, title, content, created_at) VALUES ($1, $2, $3, $4)",
                topic, title, content, now,
            )
        logger = __import__("logging").getLogger(__name__)
        logger.info(f"知识库已初始化: {len(CHUNKS)} 条")