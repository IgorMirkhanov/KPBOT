"""Регистрация Telegram webhook после деплоя на Vercel."""

from __future__ import annotations

import os
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


def main() -> None:
    if not BOT_TOKEN:
        print("Ошибка: задайте BOT_TOKEN", file=sys.stderr)
        sys.exit(1)
    if not WEBHOOK_URL:
        print(
            "Ошибка: задайте WEBHOOK_URL "
            "(например https://kpbot.vercel.app/webhook)",
            file=sys.stderr,
        )
        sys.exit(1)

    params: dict[str, str] = {"url": WEBHOOK_URL}
    if WEBHOOK_SECRET:
        params["secret_token"] = WEBHOOK_SECRET

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?{urlencode(params)}"
    with urlopen(api_url) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
