"""Tests for rate_limiter.py: the in-memory and Redis-backed limiters, the
storage-detection helper, and the @rate_limited() decorator."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import rate_limiter as rl


# --------------------------------------------------------------------------
# InMemoryRateLimiter
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_allows_up_to_max_then_blocks():
    limiter = rl.InMemoryRateLimiter(max_requests=3, window_seconds=60)

    results = [await limiter.allow(1) for _ in range(4)]

    assert results == [True, True, True, False]


@pytest.mark.asyncio
async def test_in_memory_tracks_users_independently():
    limiter = rl.InMemoryRateLimiter(max_requests=1, window_seconds=60)

    assert await limiter.allow(1) is True
    assert await limiter.allow(1) is False
    assert await limiter.allow(2) is True  # different user, own bucket


@pytest.mark.asyncio
async def test_in_memory_resets_after_window_elapses(monkeypatch):
    limiter = rl.InMemoryRateLimiter(max_requests=1, window_seconds=60)
    now = 1000.0
    monkeypatch.setattr(rl.time, "monotonic", lambda: now)

    assert await limiter.allow(1) is True
    assert await limiter.allow(1) is False

    now += 61  # past the window
    assert await limiter.allow(1) is True


# --------------------------------------------------------------------------
# AsyncRedisRateLimiter (e.g. redis.asyncio client used by aiogram RedisStorage)
# --------------------------------------------------------------------------


class FakeAsyncRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expired: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expired[key] = seconds


@pytest.mark.asyncio
async def test_async_redis_limiter_allows_then_blocks():
    redis = FakeAsyncRedis()
    limiter = rl.AsyncRedisRateLimiter(redis, max_requests=2, window_seconds=30)

    assert await limiter.allow(99) is True
    assert await limiter.allow(99) is True
    assert await limiter.allow(99) is False
    assert redis.expired["ratelimit:pdf:99"] == 30


@pytest.mark.asyncio
async def test_async_redis_limiter_fails_open_on_redis_error():
    class BrokenRedis:
        async def incr(self, key):
            raise ConnectionError("redis down")

    limiter = rl.AsyncRedisRateLimiter(BrokenRedis())
    assert await limiter.allow(1) is True  # availability over strictness


# --------------------------------------------------------------------------
# SyncRedisRateLimiter (e.g. upstash_redis client used by UpstashRestStorage)
# --------------------------------------------------------------------------


class FakeSyncRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expired: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key: str, seconds: int) -> None:
        self.expired[key] = seconds


@pytest.mark.asyncio
async def test_sync_redis_limiter_allows_then_blocks():
    redis = FakeSyncRedis()
    limiter = rl.SyncRedisRateLimiter(redis, max_requests=1, window_seconds=45)

    assert await limiter.allow(5) is True
    assert await limiter.allow(5) is False
    assert redis.expired["ratelimit:pdf:5"] == 45


# --------------------------------------------------------------------------
# build_rate_limiter_for_storage
# --------------------------------------------------------------------------


def test_build_picks_async_redis_for_aiogram_redis_storage():
    storage = SimpleNamespace(redis=FakeAsyncRedis())
    limiter = rl.build_rate_limiter_for_storage(storage)
    assert isinstance(limiter, rl.AsyncRedisRateLimiter)


def test_build_picks_sync_redis_for_upstash_storage():
    storage = SimpleNamespace(_redis=FakeSyncRedis())
    limiter = rl.build_rate_limiter_for_storage(storage)
    assert isinstance(limiter, rl.SyncRedisRateLimiter)


def test_build_falls_back_to_in_memory_for_plain_storage():
    storage = SimpleNamespace()
    limiter = rl.build_rate_limiter_for_storage(storage)
    assert isinstance(limiter, rl.InMemoryRateLimiter)


def test_get_rate_limiter_is_cached_singleton():
    rl.reset_rate_limiter()
    fake = rl.InMemoryRateLimiter()
    rl._rate_limiter = fake
    assert rl.get_rate_limiter() is fake
    rl.reset_rate_limiter()


# --------------------------------------------------------------------------
# @rate_limited() decorator
# --------------------------------------------------------------------------


class FakeEvent:
    def __init__(self, user_id: int) -> None:
        self.from_user = SimpleNamespace(id=user_id)
        self.answer = AsyncMock()


@pytest.mark.asyncio
async def test_rate_limited_calls_handler_when_allowed():
    handler = AsyncMock()
    limiter = rl.InMemoryRateLimiter(max_requests=5)
    decorated = rl.rate_limited(limiter_factory=lambda: limiter)(handler)
    event = FakeEvent(user_id=1)

    await decorated(event, "extra_arg")

    handler.assert_awaited_once_with(event, "extra_arg")
    event.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_rate_limited_blocks_handler_when_denied():
    handler = AsyncMock()
    limiter = rl.InMemoryRateLimiter(max_requests=0)
    decorated = rl.rate_limited(limiter_factory=lambda: limiter)(handler)
    event = FakeEvent(user_id=1)

    await decorated(event)

    handler.assert_not_called()
    event.answer.assert_awaited_once_with(rl.RATE_LIMIT_MESSAGE)


@pytest.mark.asyncio
async def test_rate_limited_enforces_limit_across_calls():
    handler = AsyncMock()
    limiter = rl.InMemoryRateLimiter(max_requests=2)
    decorated = rl.rate_limited(limiter_factory=lambda: limiter)(handler)
    event = FakeEvent(user_id=1)

    for _ in range(2):
        await decorated(event)
    await decorated(event)  # 3rd call, over the limit

    assert handler.await_count == 2
    event.answer.assert_awaited_once_with(rl.RATE_LIMIT_MESSAGE)
