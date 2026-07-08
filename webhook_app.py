"""Shared webhook processing logic for Vercel and local testing."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from aiogram.types import Update

from bot_setup import create_bot_and_dispatcher
from config import WEBHOOK_SECRET

logger = logging.getLogger(__name__)
IS_SERVERLESS = bool(os.getenv("VERCEL"))


def verify_secret(headers: dict[str, str]) -> bool:
    if not WEBHOOK_SECRET:
        return True
    for key, value in headers.items():
        if key.lower() == "x-telegram-bot-api-secret-token":
            return value.strip() == WEBHOOK_SECRET
    return False


async def process_update(update_data: dict) -> None:
    """Fresh Bot session per request — required for Vercel serverless."""
    bot, dp = create_bot_and_dispatcher()
    try:
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()


async def handle_webhook_post(body: bytes, headers: dict[str, str]) -> tuple[int, bytes]:
    if not verify_secret(headers):
        logger.warning("Webhook rejected: secret mismatch")
        return 403, b"Forbidden"

    try:
        update_data = json.loads(body.decode("utf-8") or "{}")
        update_id = update_data.get("update_id", "?")
        logger.info("Processing update_id=%s", update_id)
        await process_update(update_data)
        return 200, b"OK"
    except Exception:
        logger.exception("Webhook processing failed")
        return 500, b"Internal Server Error"


def _run_async(coro) -> tuple[int, bytes]:
    """New event loop per invocation — avoids 'loop is closed' on warm instances."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def handle_webhook_post_sync(body: bytes, headers: dict[str, str]) -> tuple[int, bytes]:
    return _run_async(handle_webhook_post(body, headers))
