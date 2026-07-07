import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, REDIS_URL
from handlers import router

logger = logging.getLogger(__name__)


def _create_storage() -> BaseStorage:
    if REDIS_URL:
        try:
            from redis.asyncio import Redis
            from aiogram.fsm.storage.redis import RedisStorage

            redis = Redis.from_url(REDIS_URL, decode_responses=True)
            logger.info("FSM storage: Redis")
            return RedisStorage(redis=redis)
        except Exception:
            logger.exception("Не удалось подключить Redis, используется MemoryStorage")
    logger.info("FSM storage: Memory")
    return MemoryStorage()


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Укажите переменную окружения BOT_TOKEN.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=_create_storage())
    dp.include_router(router)
    return bot, dp
