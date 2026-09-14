"""Tests for webhook_app.py: fail-closed startup behavior and secret
verification.

The fail-closed check runs at *import* time, so the two startup tests spawn
a subprocess with a clean interpreter/environment rather than importing the
already-cached module in-process.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_IMPORT_SNIPPET = "import webhook_app"


def _run_import(env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _IMPORT_SNIPPET],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_import_fails_when_webhook_secret_unset(monkeypatch):
    import os

    env = dict(os.environ)
    env.pop("WEBHOOK_SECRET", None)
    env["BOT_TOKEN"] = "123456:TEST-TOKEN"

    result = _run_import(env)

    assert result.returncode != 0
    assert "WEBHOOK_SECRET" in result.stderr
    assert "RuntimeError" in result.stderr


def test_import_fails_when_webhook_secret_blank():
    import os

    env = dict(os.environ)
    env["WEBHOOK_SECRET"] = "   "  # config.py strips it -> becomes empty
    env["BOT_TOKEN"] = "123456:TEST-TOKEN"

    result = _run_import(env)

    assert result.returncode != 0
    assert "RuntimeError" in result.stderr


def test_import_succeeds_when_webhook_secret_set():
    import os

    env = dict(os.environ)
    env["WEBHOOK_SECRET"] = "a-real-secret"
    env["BOT_TOKEN"] = "123456:TEST-TOKEN"

    result = _run_import(env)

    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------
# verify_secret — exercised in-process against the module already imported
# by conftest.py with WEBHOOK_SECRET set.
# --------------------------------------------------------------------------


@pytest.fixture()
def configured_secret(monkeypatch):
    import webhook_app

    monkeypatch.setattr(webhook_app, "WEBHOOK_SECRET", "expected-secret")
    return webhook_app


def test_verify_secret_accepts_matching_header(configured_secret):
    headers = {"X-Telegram-Bot-Api-Secret-Token": "expected-secret"}
    assert configured_secret.verify_secret(headers) is True


def test_verify_secret_is_case_insensitive_header_name(configured_secret):
    headers = {"x-telegram-bot-api-secret-token": "expected-secret"}
    assert configured_secret.verify_secret(headers) is True


def test_verify_secret_rejects_mismatched_value(configured_secret):
    headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"}
    assert configured_secret.verify_secret(headers) is False


def test_verify_secret_rejects_missing_header(configured_secret):
    assert configured_secret.verify_secret({}) is False
