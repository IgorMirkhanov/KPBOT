"""Register Telegram webhook after Vercel deploy."""

from __future__ import annotations

import os
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

try:
    from dotenv import load_dotenv

    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(os.path.join(_ROOT, ".env"))
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()


def main() -> None:
    if not BOT_TOKEN:
        print("Error: set BOT_TOKEN", file=sys.stderr)
        sys.exit(1)
    if not WEBHOOK_URL:
        print("Error: set WEBHOOK_URL", file=sys.stderr)
        sys.exit(1)

    with urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true") as r:
        print("deleteWebhook:", r.read().decode("utf-8"))

    params: dict[str, str] = {"url": WEBHOOK_URL}
    if WEBHOOK_SECRET:
        params["secret_token"] = WEBHOOK_SECRET

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?{urlencode(params)}"
    with urlopen(api_url) as response:
        print("setWebhook:", response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
