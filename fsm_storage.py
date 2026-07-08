"""FSM storage backends for local polling and Vercel serverless."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType

logger = logging.getLogger(__name__)

_STATE_TTL = 86400


def _storage_key(prefix: str, key: StorageKey, suffix: str) -> str:
    return f"{prefix}:{key.bot_id}:{key.chat_id}:{key.user_id}:{suffix}"


def _state_value(state: StateType) -> str:
    if isinstance(state, State):
        return state.state
    return str(state)


class UpstashRestStorage(BaseStorage):
    """aiogram FSM storage via Upstash HTTP REST API (serverless-friendly)."""

    def __init__(self, url: str, token: str) -> None:
        from upstash_redis import Redis

        self._redis = Redis(url=url, token=token)

    async def _run(self, func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        redis_key = _storage_key("fsm", key, "state")
        if state is None:
            await self._run(self._redis.delete, redis_key)
        else:
            await self._run(self._redis.set, redis_key, _state_value(state), ex=_STATE_TTL)

    async def get_state(self, key: StorageKey) -> str | None:
        redis_key = _storage_key("fsm", key, "state")
        value = await self._run(self._redis.get, redis_key)
        return value if value else None

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        redis_key = _storage_key("fsm", key, "data")
        if data:
            await self._run(
                self._redis.set,
                redis_key,
                json.dumps(data, ensure_ascii=False),
                ex=_STATE_TTL,
            )
        else:
            await self._run(self._redis.delete, redis_key)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        redis_key = _storage_key("fsm", key, "data")
        raw = await self._run(self._redis.get, redis_key)
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        return json.loads(raw)

    async def update_data(self, key: StorageKey, data: dict[str, Any]) -> dict[str, Any]:
        current = await self.get_data(key)
        current.update(data)
        await self.set_data(key, current)
        return current

    async def close(self) -> None:
        return None
