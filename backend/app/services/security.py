"""安全模块：接口限流与登录失败锁定防刷。"""
import os
import threading
import time
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.database.base import db_manager

LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_MINUTES = 15


class InMemoryRateLimiter:
    """进程内滑动窗口限流器（单实例部署足够，重启后自动清零）。"""

    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            window = [t for t in self._hits.get(key, []) if now - t < window_seconds]
            if len(window) >= limit:
                self._hits[key] = window
                return False
            window.append(now)
            self._hits[key] = window
            return True

    def reset(self, key: str):
        with self._lock:
            self._hits.pop(key, None)


class RedisRateLimiter:
    """基于 Redis 的分布式限流；连接异常时自动降级到内存限流。"""

    def __init__(self, url: str, fallback: InMemoryRateLimiter):
        import redis
        self._client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=1)
        self._fallback = fallback

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        try:
            redis_key = f"rate_limit:{key}"
            current = self._client.incr(redis_key)
            if current == 1:
                self._client.expire(redis_key, window_seconds)
            return int(current) <= limit
        except Exception:
            return self._fallback.allow(key, limit, window_seconds)


_memory_limiter = InMemoryRateLimiter()


def _build_rate_limiter():
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        try:
            return RedisRateLimiter(redis_url, _memory_limiter)
        except Exception:
            pass
    return _memory_limiter


rate_limiter = _build_rate_limiter()


def check_rate_limit(key: str, limit: int, window_seconds: int = 60):
    """不满足配额时抛出 429，避免在业务代码里重复写错误响应。"""
    if not rate_limiter.allow(key, limit, window_seconds):
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后重试",
        )


async def is_login_locked(phone: str):
    now = datetime.utcnow()
    async with db_manager.get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT failed_count, locked_until FROM login_attempts WHERE phone = $1",
            phone,
        )
    if row and row["locked_until"] and row["locked_until"] > now:
        wait_seconds = int((row["locked_until"] - now).total_seconds())
        return True, wait_seconds
    return False, 0


async def record_login_failure(phone: str):
    now = datetime.utcnow()
    async with db_manager.get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT failed_count FROM login_attempts WHERE phone = $1",
            phone,
        )
        if row:
            failed = row["failed_count"] + 1
            locked_until = (
                now + timedelta(minutes=LOGIN_LOCK_MINUTES)
                if failed >= LOGIN_MAX_FAILURES
                else None
            )
            await conn.execute(
                """
                UPDATE login_attempts
                SET failed_count = $1, locked_until = $2, last_attempt = $3
                WHERE phone = $4
                """,
                failed, locked_until, now, phone,
            )
        else:
            await conn.execute(
                """
                INSERT INTO login_attempts (phone, failed_count, locked_until, last_attempt)
                VALUES ($1, 1, NULL, $2)
                """,
                phone, now,
            )


async def clear_login_failures(phone: str):
    async with db_manager.get_connection() as conn:
        await conn.execute(
            "DELETE FROM login_attempts WHERE phone = $1",
            phone,
        )
