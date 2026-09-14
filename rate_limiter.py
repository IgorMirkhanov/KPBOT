"""Per-user rate limiting for PDF-generation requests.

Reuses whichever storage the FSM dispatcher already has instead of adding a
new dependency:

- aiogram's ``RedisStorage`` (backed by ``redis.asyncio.Redis``) -> counters
  live in the same Redis instance, via async INCR/EXPIRE.
- ``UpstashRestStorage`` (backed by the sync ``upstash_redis.Redis`` HTTP
  client) -> same idea, calls run through ``asyncio.to_thread``.
- ``MemoryStorage`` (local dev without Redis configured) -> a small
  in-process sliding window, since there is nothing else to reuse.

All limiters implement the same ``async def allow(user_id) -> bool`` API.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from collections import deque
from typing import Awaitable, Callable, Protocol

logger = logging.getLogger(__name__)

RATE_LIMIT_MAX_REQUESTS = 5
RATE_LIMIT_WINDOW_SECONDS = 60

RATE_LIMIT_MESSAGE = (
    "⏳ Слишком много запросов на генерацию КП. "
    "Подождите немного и попробуйте снова."
)


class RateLimiter(Protocol):
    async def allow(self, user_id: int) -> bool: ...


class InMemoryRateLimiter:
    """Sliding-window limiter kept in process memory.

    Used only when no Redis-backed storage is available (e.g. local polling
    without REDIS_URL/Upstash configured). Not shared across serverless
    instances — acceptable as a local-dev fallback, not for production.
    """

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_MAX_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[int, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits.setdefault(user_id, deque())
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True


class AsyncRedisRateLimiter:
    """Fixed-window counter backed by an async (``redis.asyncio``) client."""

    def __init__(
        self,
        redis_client,
        max_requests: int = RATE_LIMIT_MAX_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
        key_prefix: str = "ratelimit:pdf",
    ) -> None:
        self._redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix

    async def allow(self, user_id: int) -> bool:
        key = f"{self.key_prefix}:{user_id}"
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, self.window_seconds)
            return count <= self.max_requests
        except Exception:
            logger.exception("Redis rate limit check failed, allowing request")
            return True


class SyncRedisRateLimiter:
    """Fixed-window counter backed by a sync client (e.g. upstash_redis),
    run off the event loop via asyncio.to_thread."""

    def __init__(
        self,
        redis_client,
        max_requests: int = RATE_LIMIT_MAX_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
        key_prefix: str = "ratelimit:pdf",
    ) -> None:
        self._redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix

    async def allow(self, user_id: int) -> bool:
        key = f"{self.key_prefix}:{user_id}"
        try:
            count = await asyncio.to_thread(self._redis.incr, key)
            if count == 1:
                await asyncio.to_thread(self._redis.expire, key, self.window_seconds)
            return count <= self.max_requests
        except Exception:
            logger.exception("Redis rate limit check failed, allowing request")
            return True


_rate_limiter: RateLimiter | None = None


def build_rate_limiter_for_storage(storage) -> RateLimiter:
    """Pick the right limiter implementation for the given FSM storage instance."""
    redis_client = getattr(storage, "redis", None)  # aiogram RedisStorage
    if redis_client is not None:
        return AsyncRedisRateLimiter(redis_client)

    upstash_client = getattr(storage, "_redis", None)  # UpstashRestStorage
    if upstash_client is not None:
        return SyncRedisRateLimiter(upstash_client)

    return InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Singleton limiter, built lazily from the dispatcher's active storage."""
    global _rate_limiter
    if _rate_limiter is None:
        from bot_setup import get_dispatcher

        _rate_limiter = build_rate_limiter_for_storage(get_dispatcher().storage)
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Test helper: drop the cached singleton so it is rebuilt on next use."""
    global _rate_limiter
    _rate_limiter = None


def rate_limited(
    limiter_factory: Callable[[], RateLimiter] = get_rate_limiter,
    reject_message: str = RATE_LIMIT_MESSAGE,
) -> Callable:
    """Decorator for aiogram handlers: blocks a user past the request limit.

    Works for both ``Message`` and ``CallbackQuery`` handlers — the decorated
    event's ``from_user.id`` identifies the caller.
    """

    def decorator(handler: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
        @functools.wraps(handler)
        async def wrapper(event, *args, **kwargs):
            user = getattr(event, "from_user", None)
            if user is not None:
                limiter = limiter_factory()
                allowed = await limiter.allow(user.id)
                if not allowed:
                    logger.info("Rate limit hit for user_id=%s", user.id)
                    answer = getattr(event, "answer", None)
                    if answer is not None:
                        # Works for both Message.answer(text) and
                        # CallbackQuery.answer(text) — text is positional in both.
                        await answer(reject_message)
                    return
            return await handler(event, *args, **kwargs)

        return wrapper

    return decorator
