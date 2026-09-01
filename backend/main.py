"""
FastAPI 主入口文件
AI 面试助手后端服务
"""

import os
import logging
import signal
import sys
import asyncio
import time

# Windows 下 psycopg 异步连接池需要 Selector 事件循环
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, upload, sessions, config, resume, voice_chat, auth, report, account
from app.api.auth import decode_token
from app.models.schemas import ErrorResponse
from app.database import db_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    # 启动时执行
    logger.info("AI 面试助手后端服务启动中...")
    
    # 初始化数据库
    from app.database import init_database
    await init_database()
    
    # 初始化 RAG 知识库
    from app.services.knowledge_base import ensure_knowledge_base
    await ensure_knowledge_base()
    # 确保数据目录存在
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, "resumes"), exist_ok=True)
    
    # 确保静态文件目录存在
    static_dir = os.path.join(os.getcwd(), "static")
    os.makedirs(os.path.join(static_dir, "audio"), exist_ok=True)
    
    logger.info("数据目录和静态目录初始化完成")
    
    # 建立数据库持久连接
    await db_manager.connect()
    
    yield
    
    # 关闭时执行
    logger.info("AI 面试助手后端服务关闭中...")
    
    # 清理资源
    await cleanup_resources()

async def cleanup_resources():
    """
    清理所有资源，including数据库连接和图实例
    """
    logger.info("正在清理资源...")
    
    # 关闭全局 checkpointer 和连接
    try:
        from app.core.memory import close_checkpointer
        await close_checkpointer()
        logger.info("✓ Checkpointer 已关闭")
    except Exception as e:
        logger.error(f"✗ 关闭 checkpointer 时出错: {e}")
    
    # 清理图实例列表
    try:
        from app.core.graph import clear_graph_instances
        clear_graph_instances()
        logger.info("✓ 图实例列表已清空")
    except Exception as e:
        logger.error(f"✗ 清理图实例时出错: {e}")
    
    # 关闭数据库持久连接
    try:
        await db_manager.disconnect()
        logger.info("✓ 数据库连接已关闭")
    except Exception as e:
        logger.error(f"✗ 关闭数据库连接时出错: {e}")
    
    logger.info("资源清理完成")

def handle_signal(signum, frame):
    """
    处理系统信号，实现优雅关闭
    """
    logger.info(f"接收到信号 {signum}，开始优雅关闭...")
    
    # 使用线程池来执行异步清理
    import threading
    
    def run_cleanup():
        """在新线程中运行清理函数"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行清理函数
            loop.run_until_complete(cleanup_resources())
            logger.info("资源清理完成")
            
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")
        finally:
            try:
                loop.close()
            except:
                pass
    
    # 启动清理线程
    cleanup_thread = threading.Thread(target=run_cleanup)
    cleanup_thread.start()
    
    # 等待清理线程完成（最多等待3秒）
    cleanup_thread.join(timeout=3)
    
    # 退出程序
    sys.exit(0)


# 创建 FastAPI 应用实例
app = FastAPI(
    title="AI 面试助手 API",
    description="基于 FastAPI + LangGraph 的智能面试系统后端",
    version="1.0.0",
    lifespan=lifespan
)

# 登录校验中间件：业务接口必须携带 Bearer 令牌，并把用户ID注入 X-User-ID
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    public_paths = ("/health", "/docs", "/redoc", "/openapi.json", "/static", "/api/auth/")
    if request.method == "OPTIONS" or path == "/" or path.startswith(("/health", "/docs", "/redoc", "/openapi.json", "/static")) or path in ("/api/auth/send-code", "/api/auth/register", "/api/auth/login"):
        return await call_next(request)

    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "message": "未登录或登录已过期，请重新登录"},
        )
    payload = decode_token(authorization[7:])
    if not payload:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "message": "未登录或登录已过期，请重新登录"},
        )

    user_id = str(payload.get("sub", "default_user"))
    request.state.user_id = user_id
    headers = [(k, v) for k, v in request.scope["headers"] if k.lower() != b"x-user-id"]
    headers.append((b"x-user-id", user_id.encode()))
    request.scope["headers"] = headers
    return await call_next(request)

# 配置 CORS - 允许的前端域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://interview.1624899.fun",  # Cloudflare Pages 域名
        "https://ai-interview-63l.pages.dev",           # Cloudflare Pages 主域名
        "http://localhost:3000",                         # 本地开发
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# 请求日志与用量统计中间件
@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    path = request.url.path
    if path == "/health" or path.startswith(("/docs", "/redoc", "/openapi.json", "/static")):
        return await call_next(request)

    import time as _time
    from app.services.observability import log_json, record_request
    from app.services.security import rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(f"api:{client_ip}:{path}", 120, 60):
        return JSONResponse(
            status_code=429,
            content={"error": "RateLimitExceeded", "message": "请求过于频繁，请稍后重试"},
        )
    start = _time.perf_counter()
    response = await call_next(request)
    duration_ms = (_time.perf_counter() - start) * 1000
    user_id = getattr(request.state, "user_id", "anonymous")
    log_json(
        "http_request",
        user_id=user_id,
        method=request.method,
        path=path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    await record_request(
        user_id=user_id,
        method=request.method,
        path=path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response
# 全局异常处理器
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail if isinstance(exc.detail, dict) else {
            "error": "HTTPException",
            "message": exc.detail
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """通用异常处理"""
    logger.error(f"未处理的异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "服务器内部错误,请稍后重试"
        }
    )


# 根路径
@app.get("/")
async def root():
    """
    根路径，返回 API 信息
    """
    return {
        "message": "AI 面试助手 API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


# 健康检查
@app.get("/health")
async def health_check():
    """
    健康检查端点
    """
    return {
        "status": "healthy",
        "message": "服务运行正常"
    }



# 注册路由
from fastapi.staticfiles import StaticFiles

# 注册路由
app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(sessions.router)
app.include_router(config.router)
app.include_router(resume.router)
app.include_router(voice_chat.router)
app.include_router(auth.router)
app.include_router(report.router)
app.include_router(account.router)

# 挂载静态文件目录
static_dir = os.path.join(os.getcwd(), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 启动信息
if __name__ == "__main__":
    import uvicorn
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # 从环境变量读取配置，如果没有则使用默认值
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    logger.info(f"启动服务器: http://{host}:{port}")
    logger.info(f"API 文档: http://{host}:{port}/docs")
    logger.info("按 Ctrl+C 可以正常关闭服务器")
    
    try:
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=debug,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("接收到键盘中断，正在关闭...")
    except Exception as e:
        logger.error(f"服务器运行出错: {e}")
    finally:
        logger.info("服务器已关闭")