"""Vercel serverless entrypoint для Telegram webhook."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler

# Корень проекта в PYTHONPATH (Vercel запускает из /var/task)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from aiogram.types import Update

from bot_setup import create_bot_and_dispatcher
from config import WEBHOOK_SECRET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_bot = None
_dp = None


def _get_app() -> tuple:
    global _bot, _dp
    if _bot is None or _dp is None:
        _bot, _dp = create_bot_and_dispatcher()
    return _bot, _dp


async def _process_update(update_data: dict) -> None:
    bot, dp = _get_app()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes = b"", content_type: str = "text/plain") -> None:
        self.send_response(code)
        if body:
            self.send_header("Content-Type", content_type)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self) -> None:
        self._send(200, b"KPBOT webhook is running")

    def do_POST(self) -> None:
        if WEBHOOK_SECRET:
            secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if secret != WEBHOOK_SECRET:
                self._send(403, b"Forbidden")
                return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            update_data = json.loads(raw.decode("utf-8"))
            asyncio.run(_process_update(update_data))
            self._send(200)
        except Exception:
            logger.exception("Webhook processing failed")
            self._send(500, b"Internal Server Error")
