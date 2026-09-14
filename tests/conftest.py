"""Pytest bootstrap: make the project importable and provide safe default
environment variables before any project module is imported.

config.py and webhook_app.py read environment variables at *import* time
(webhook_app even raises if WEBHOOK_SECRET is missing — see
test_webhook_app.py for the dedicated fail-closed tests, which unset it
explicitly via subprocess). Setting sane defaults here, before test modules
are collected, keeps the rest of the suite import-safe.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret")
