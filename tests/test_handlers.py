"""Tests for handlers.py: input validation and the rate-limited PDF trigger."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import handlers
import rate_limiter


class FakeUser(SimpleNamespace):
    id: int = 42


class FakeMessage:
    def __init__(self, text: str, user_id: int = 42) -> None:
        self.text = text
        self.from_user = FakeUser(id=user_id)
        self.answer = AsyncMock()
        self.answer_document = AsyncMock()


class FakeState:
    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})
        self.update_data = AsyncMock(side_effect=self._update_data)
        self.set_state = AsyncMock()
        self.get_data = AsyncMock(side_effect=self._get_data)
        self.clear = AsyncMock()

    async def _update_data(self, **kwargs):
        self._data.update(kwargs)

    async def _get_data(self):
        return dict(self._data)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    rate_limiter.reset_rate_limiter()
    yield
    rate_limiter.reset_rate_limiter()


# --------------------------------------------------------------------------
# company name validation
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_company_name_too_short_asks_again():
    message = FakeMessage(" a ")
    state = FakeState()

    await handlers.process_company_name(message, state)

    message.answer.assert_awaited_once()
    assert "короткое" in message.answer.await_args.args[0]
    state.update_data.assert_not_awaited()
    state.set_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_company_name_min_length_boundary_accepted():
    message = FakeMessage("ok")  # exactly 2 chars — the documented minimum
    state = FakeState()

    await handlers.process_company_name(message, state)

    state.update_data.assert_awaited_once_with(company_name="ok")
    state.set_state.assert_awaited_once_with(handlers.FormStates.waiting_for_price_mode)


@pytest.mark.asyncio
async def test_company_name_valid_strips_whitespace():
    message = FakeMessage("  ACME LLC  ")
    state = FakeState()

    await handlers.process_company_name(message, state)

    state.update_data.assert_awaited_once_with(company_name="ACME LLC")


# --------------------------------------------------------------------------
# custom price validation (sanitize_price_digits edge cases via the handler)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_price_valid_number():
    message = FakeMessage("850000")
    state = FakeState()

    await handlers.process_custom_price(message, state)

    state.update_data.assert_awaited_once_with(use_base_prices=False, custom_price=850000)
    state.set_state.assert_awaited_once_with(handlers.FormStates.waiting_for_project_deadline)
    message.answer.assert_awaited_once_with(handlers.DEADLINE_PROMPT)


@pytest.mark.asyncio
async def test_custom_price_with_spaces_and_currency_sanitized():
    message = FakeMessage("850 000 тг")
    state = FakeState()

    await handlers.process_custom_price(message, state)

    state.update_data.assert_awaited_once_with(use_base_prices=False, custom_price=850000)


@pytest.mark.asyncio
async def test_custom_price_non_numeric_rejected():
    message = FakeMessage("бесплатно")
    state = FakeState()

    await handlers.process_custom_price(message, state)

    message.answer.assert_awaited_once()
    assert "Некорректная цена" in message.answer.await_args.args[0]
    state.update_data.assert_not_awaited()


@pytest.mark.asyncio
async def test_custom_price_zero_rejected():
    message = FakeMessage("0")
    state = FakeState()

    await handlers.process_custom_price(message, state)

    message.answer.assert_awaited_once()
    assert "Некорректная цена" in message.answer.await_args.args[0]


# --------------------------------------------------------------------------
# project deadline validation (undecorated: pure business logic, no
# rate-limiter / generate_pdf involvement)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_deadline_too_short_asks_again(monkeypatch):
    generate_pdf_mock = AsyncMock()
    monkeypatch.setattr(handlers, "generate_pdf", generate_pdf_mock)
    message = FakeMessage(" x ")
    state = FakeState()

    await handlers.process_project_deadline.__wrapped__(message, state)

    message.answer.assert_awaited_once()
    assert "Введите срок" in message.answer.await_args.args[0]
    generate_pdf_mock.assert_not_called()


# --------------------------------------------------------------------------
# rate limiting on the PDF-generation trigger
# --------------------------------------------------------------------------


class FakeLimiter:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls: list[int] = []

    async def allow(self, user_id: int) -> bool:
        self.calls.append(user_id)
        return self.allowed


@pytest.mark.asyncio
async def test_process_project_deadline_blocked_when_rate_limited(monkeypatch):
    rate_limiter._rate_limiter = FakeLimiter(allowed=False)
    generate_pdf_mock = AsyncMock()
    monkeypatch.setattr(handlers, "generate_pdf", generate_pdf_mock)

    message = FakeMessage("31.12.2026", user_id=7)
    state = FakeState(
        {
            "company_name": "ACME",
            "selected_services": ["smm_junior"],
            "use_base_prices": True,
        }
    )

    await handlers.process_project_deadline(message, state)

    message.answer.assert_awaited_once_with(rate_limiter.RATE_LIMIT_MESSAGE)
    generate_pdf_mock.assert_not_called()
    message.answer_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_project_deadline_generates_pdf_when_allowed(monkeypatch):
    rate_limiter._rate_limiter = FakeLimiter(allowed=True)
    monkeypatch.setattr(handlers, "generate_pdf", lambda data: "/tmp/fake.pdf")
    monkeypatch.setattr(handlers.types, "FSInputFile", lambda path, filename=None: path)

    message = FakeMessage("31.12.2026", user_id=7)
    state = FakeState(
        {
            "company_name": "ACME",
            "selected_services": ["smm_junior"],
            "use_base_prices": True,
        }
    )

    await handlers.process_project_deadline(message, state)

    message.answer_document.assert_awaited_once()
    state.clear.assert_awaited_once()
