"""自定义 asyncio loop factory。

uvicorn 在 Windows 上默认使用 ProactorEventLoop，
而 psycopg 异步连接池需要 SelectorEventLoop，因此本地开发强制切到 Selector。
"""
import asyncio


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()