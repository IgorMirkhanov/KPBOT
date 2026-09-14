"""Shared webhook processing logic for Vercel and local testing."""

from __future__ import annotations

import asyncio
import json
import logging

from aiogram.types import Update

from bot_setup import create_bot, get_dispatcher
from config import WEBHOOK_SECRET

logger = logging.getLogger(__name__)


def require_webhook_secret_configured() -> None:
    """Fail loudly at startup rather than fail open on every webhook request.

    Without WEBHOOK_SECRET set, verify_secret() has no way to authenticate
    Telegram's requests. Refuse to serve traffic instead of silently
    accepting unauthenticated webhook calls.
    """
    if not WEBHOOK_SECRET:
        raise RuntimeError(
            "WEBHOOK_SECRET is not set. Refusing to start: without it the "
            "webhook cannot verify requests actually come from Telegram. "
            "Set the WEBHOOK_SECRET environment variable."
        )


require_webhook_secret_configured()


def verify_secret(headers: dict[str, str]) -> bool:
    for key, value in headers.items():
        if key.lower() == "x-telegram-bot-api-secret-token":
            return value.strip() == WEBHOOK_SECRET
    return False


async def process_update(update_data: dict) -> None:
    """Fresh Bot per request, singleton Dispatcher — Vercel serverless pattern."""
    bot = create_bot()
    dp = get_dispatcher()
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
        logger.info("Processing update_id=%s", update_data.get("update_id", "?"))
        await process_update(update_data)
        return 200, b"OK"
    except Exception:
        logger.exception("Webhook processing failed")
        return 500, b"Internal Server Error"


def _run_async(coro) -> tuple[int, bytes]:
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
