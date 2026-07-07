import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, get_redis_url, get_upstash_rest_credentials
from fsm_storage import UpstashRestStorage
from handlers import router

logger = logging.getLogger(__name__)


def _create_storage() -> BaseStorage:
    redis_url = get_redis_url()
    if redis_url:
        try:
            from redis.asyncio import Redis
            from aiogram.fsm.storage.redis import RedisStorage

            redis = Redis.from_url(redis_url, decode_responses=True)
            logger.info("FSM storage: Redis TCP")
            return RedisStorage(redis=redis)
        except Exception:
            logger.exception("Redis TCP failed, trying Upstash REST")

    rest_url, rest_token = get_upstash_rest_credentials()
    if rest_url and rest_token:
        try:
            logger.info("FSM storage: Upstash REST")
            return UpstashRestStorage(rest_url, rest_token)
        except Exception:
            logger.exception("Upstash REST failed, using MemoryStorage")

    logger.warning("FSM storage: Memory (not suitable for Vercel production)")
    return MemoryStorage()


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set. Set BOT_TOKEN environment variable.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=_create_storage())
    dp.include_router(router)
    return bot, dp
