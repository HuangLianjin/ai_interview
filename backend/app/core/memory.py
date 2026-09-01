"""
LangGraph 记忆模块

使用 PostgreSQL checkpointer 持久化 LangGraph 状态：
- 面试中途刷新/断线/服务重启后可以基于 checkpoint 恢复
- 会话业务数据仍通过 SessionService 持久化到 PostgreSQL
"""
import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from ..database.config import DATABASE_URL

logger = logging.getLogger(__name__)

# 全局单例 checkpointer 实例
_global_pool: AsyncConnectionPool | None = None
_global_checkpointer: AsyncPostgresSaver | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """获取 PostgreSQL checkpointer（单例模式）。"""
    global _global_pool, _global_checkpointer

    if _global_checkpointer is None:
        dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        _global_pool = AsyncConnectionPool(conninfo=dsn, max_size=10, open=False, kwargs={"autocommit": True})
        await _global_pool.open()
        _global_checkpointer = AsyncPostgresSaver(_global_pool)
        await _global_checkpointer.setup()
        logger.info("LangGraph 使用 PostgreSQL checkpointer（支持面试恢复）")

    return _global_checkpointer


# 向后兼容的别名
async def get_async_sqlite_saver(db_path: str = None):
    """向后兼容的别名。"""
    return await get_checkpointer()


async def close_checkpointer():
    """关闭全局 checkpointer 和连接池。"""
    global _global_pool, _global_checkpointer
    if _global_pool is not None:
        try:
            await _global_pool.close()
        except Exception as e:
            logger.warning(f"关闭 PostgreSQL checkpointer 连接池失败: {e}")
    _global_pool = None
    _global_checkpointer = None
    logger.info("Checkpointer 已关闭")


def reset_checkpointer():
    """重置全局 checkpointer（用于测试）。"""
    global _global_pool, _global_checkpointer
    _global_pool = None
    _global_checkpointer = None
    logger.info("Checkpointer 已重置")