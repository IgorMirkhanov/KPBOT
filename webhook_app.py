"""Shared webhook processing logic for Vercel and local testing."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiogram.types import Update

from bot_setup import create_bot_and_dispatcher
from config import WEBHOOK_SECRET

logger = logging.getLogger(__name__)

_bot = None
_dp = None


def get_app() -> tuple[Any, Any]:
    global _bot, _dp
    if _bot is None or _dp is None:
        _bot, _dp = create_bot_and_dispatcher()
    return _bot, _dp


async def process_update(update_data: dict) -> None:
    bot, dp = get_app()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)


def verify_secret(headers: dict[str, str]) -> bool:
    if not WEBHOOK_SECRET:
        return True
    for key, value in headers.items():
        if key.lower() == "x-telegram-bot-api-secret-token":
            return value.strip() == WEBHOOK_SECRET
    return False


async def handle_webhook_post(body: bytes, headers: dict[str, str]) -> tuple[int, bytes]:
    if not verify_secret(headers):
        return 403, b"Forbidden"

    try:
        update_data = json.loads(body.decode("utf-8") or "{}")
        await process_update(update_data)
        return 200, b"OK"
    except Exception:
        logger.exception("Webhook processing failed")
        return 500, b"Internal Server Error"


def handle_webhook_post_sync(body: bytes, headers: dict[str, str]) -> tuple[int, bytes]:
    return asyncio.run(handle_webhook_post(body, headers))
