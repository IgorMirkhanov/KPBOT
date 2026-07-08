import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, get_redis_url, get_upstash_rest_credentials
from fsm_storage import UpstashRestStorage
from handlers import router

logger = logging.getLogger(__name__)

_dispatcher: Dispatcher | None = None


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


def get_dispatcher() -> Dispatcher:
    """Singleton Dispatcher — router attaches once per warm serverless instance."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher(storage=_create_storage())
        _dispatcher.include_router(router)
        logger.info("Dispatcher initialized")
    return _dispatcher


def create_bot() -> Bot:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set. Set BOT_TOKEN environment variable.")
    return Bot(token=BOT_TOKEN)


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    """For local polling in main.py."""
    return create_bot(), get_dispatcher()
