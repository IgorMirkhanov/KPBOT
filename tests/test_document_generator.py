"""Tests for document_generator.py: price sanitization, validation and the
PDF-stamping logic (with the actual PDF write mocked out)."""

from __future__ import annotations

from pathlib import Path

import pytest

import document_generator as dg


# --------------------------------------------------------------------------
# sanitize_price_digits
# --------------------------------------------------------------------------


class TestSanitizePriceDigits:
    def test_plain_int(self):
        assert dg.sanitize_price_digits(850000) == 850000

    def test_float_rounds(self):
        assert dg.sanitize_price_digits(850000.6) == 850001

    def test_string_with_spaces_and_currency(self):
        assert dg.sanitize_price_digits("850 000 тг") == 850000

    def test_string_plain_digits(self):
        assert dg.sanitize_price_digits("850000") == 850000

    def test_string_with_leading_trailing_junk(self):
        assert dg.sanitize_price_digits("  price: 1234abc ") == 1234

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            dg.sanitize_price_digits(0)

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            dg.sanitize_price_digits(-5)

    def test_bool_raises(self):
        # bool is an int subclass in Python — must be rejected explicitly.
        with pytest.raises(ValueError):
            dg.sanitize_price_digits(True)

    def test_non_numeric_string_raises(self):
        with pytest.raises(ValueError):
            dg.sanitize_price_digits("бесплатно")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            dg.sanitize_price_digits("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            dg.sanitize_price_digits("   ")


# --------------------------------------------------------------------------
# format_tenge / totals
# --------------------------------------------------------------------------


def test_format_tenge_formats_with_spaces():
    assert dg.format_tenge(1234567) == "1 234 567 тг"


def test_format_tenge_zero_or_negative_is_dash():
    assert dg.format_tenge(0) == "—"
    assert dg.format_tenge(-1) == "—"


def test_calculate_selected_totals_sums_base_prices():
    total_1m, total_3m, total_6m = dg.calculate_selected_totals(["smm_junior", "context"])
    assert total_1m == dg.BASE_PRICES["smm_junior"]["val_1m"] + dg.BASE_PRICES["context"]["val_1m"]
    assert total_3m == dg.BASE_PRICES["smm_junior"]["val_3m"] + dg.BASE_PRICES["context"]["val_3m"]
    assert total_6m == dg.BASE_PRICES["smm_junior"]["val_6m"] + dg.BASE_PRICES["context"]["val_6m"]


def test_calculate_custom_packages_applies_discounts():
    price_1m, price_3m, price_6m = dg.calculate_custom_packages(100_000)
    assert price_1m == 100_000
    assert price_3m == round(100_000 * 3 * 0.9)
    assert price_6m == round(100_000 * 6 * 0.85)


# --------------------------------------------------------------------------
# validate_pdf_data
# --------------------------------------------------------------------------


def _base_payload(**overrides):
    payload = {
        "company_name": "ACME LLC",
        "project_deadline": "31.12.2026",
        "selected_services": ["smm_junior"],
        "use_base_prices": True,
    }
    payload.update(overrides)
    return payload


def test_validate_pdf_data_missing_field_raises():
    payload = _base_payload()
    del payload["company_name"]
    with pytest.raises(ValueError):
        dg.validate_pdf_data(payload)


def test_validate_pdf_data_empty_services_raises():
    with pytest.raises(ValueError):
        dg.validate_pdf_data(_base_payload(selected_services=[]))


def test_validate_pdf_data_unknown_service_raises():
    with pytest.raises(ValueError):
        dg.validate_pdf_data(_base_payload(selected_services=["not_a_real_service"]))


def test_validate_pdf_data_blank_company_name_raises():
    with pytest.raises(ValueError):
        dg.validate_pdf_data(_base_payload(company_name="   "))


def test_validate_pdf_data_custom_price_required_when_not_using_base():
    with pytest.raises(ValueError):
        dg.validate_pdf_data(_base_payload(use_base_prices=False))


def test_validate_pdf_data_custom_price_computes_totals():
    payload = dg.validate_pdf_data(
        _base_payload(use_base_prices=False, custom_price="500000")
    )
    assert payload["custom_price"] == 500_000
    assert payload["total_1m"] == 500_000
    assert payload["total_3m"] == round(500_000 * 3 * 0.9)


def test_validate_pdf_data_base_prices_computes_totals():
    payload = dg.validate_pdf_data(_base_payload(selected_services=["smm_junior", "context"]))
    expected = dg.calculate_selected_totals(["smm_junior", "context"])
    assert (payload["total_1m"], payload["total_3m"], payload["total_6m"]) == expected


# --------------------------------------------------------------------------
# PDF-stamping logic — real fitz.Rect / TEXT_ALIGN constants, but no real
# PDF I/O: page objects are lightweight fakes that just record calls.
# --------------------------------------------------------------------------


class FakePage:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_fonts(self):
        return []

    def insert_font(self, fontname=None, fontfile=None):
        self.calls.append(("insert_font", fontname, fontfile))

    def draw_rect(self, rect, color=None, fill=None, overlay=None):
        self.calls.append(("draw_rect", rect, color, fill, overlay))

    def insert_textbox(self, rect, text, fontname=None, fontsize=None, color=None, align=None):
        self.calls.append(("insert_textbox", rect, text, fontsize, color, align))
        return 1.0  # non-negative => no overflow

    def insert_text(self, pos, text, fontname=None, fontsize=None, color=None):
        self.calls.append(("insert_text", pos, text, fontsize, color))


@pytest.fixture(autouse=True)
def _fake_font(monkeypatch):
    """Point ensure_arial_font at the real bundled asset, no filesystem writes."""
    asset = Path(dg.__file__).resolve().parent / "assets" / "fonts" / "Arial.ttf"
    monkeypatch.setattr(dg, "ensure_arial_font", lambda: asset)


def _textbox_texts(page: FakePage) -> list[str]:
    return [c[2] for c in page.calls if c[0] == "insert_textbox"]


def test_write_total_row_inserts_label_and_formatted_totals():
    page = FakePage()
    budget = dg.LAYOUT_PREMIUM_V1["budget"]

    dg._write_total_row(page, budget, 1_000_000, 2_700_000, 5_100_000)

    texts = _textbox_texts(page)
    assert "ИТОГО" in texts
    assert dg.format_tenge(1_000_000) in texts
    assert dg.format_tenge(2_700_000) in texts
    assert dg.format_tenge(5_100_000) in texts
    # the row background must be masked before text is written
    assert page.calls[0][0] == "draw_rect"


def test_write_deadline_row_inserts_deadline_text():
    page = FakePage()
    budget = dg.LAYOUT_PREMIUM_V1["budget"]

    dg._write_deadline_row(page, budget, "31.12.2026")

    texts = _textbox_texts(page)
    assert "31.12.2026" in texts
    assert "Срок / дата запуска:" in texts


def test_mask_service_rows_hides_unselected_and_when_custom_price():
    page = FakePage()
    budget = dg.LAYOUT_PREMIUM_V1["budget"]

    dg._mask_service_rows(page, ["smm_junior"], use_base_prices=True, budget=budget)

    masked_rects = [c[1] for c in page.calls if c[0] == "draw_rect"]
    assert dg._rect_from_tuple(budget["service_rows"]["context"]) in masked_rects
    assert dg._rect_from_tuple(budget["service_rows"]["smm_junior"]) not in masked_rects


def test_mask_service_rows_hides_everything_when_custom_price_used():
    page = FakePage()
    budget = dg.LAYOUT_PREMIUM_V1["budget"]

    dg._mask_service_rows(page, ["smm_junior"], use_base_prices=False, budget=budget)

    masked_rects = [c[1] for c in page.calls if c[0] == "draw_rect"]
    assert dg._rect_from_tuple(budget["service_rows"]["smm_junior"]) in masked_rects


def test_inject_cover_writes_company_name():
    page = FakePage()
    dg._inject_cover(page, "ACME LLC", dg.LAYOUT_PREMIUM_V1)
    insert_text_calls = [c for c in page.calls if c[0] == "insert_text"]
    assert insert_text_calls[0][2] == "ACME LLC"


def test_resolve_layout_premium_and_legacy():
    assert dg._resolve_layout(9) is dg.LAYOUT_PREMIUM_V1
    assert dg._resolve_layout(21) is dg.LAYOUT_LEGACY_V1


def test_resolve_layout_unsupported_page_count_raises():
    with pytest.raises(ValueError):
        dg._resolve_layout(3)


# --------------------------------------------------------------------------
# generate_pdf — full pipeline with fitz.open mocked out entirely.
# --------------------------------------------------------------------------


class FakeDocument:
    """Stands in for a fitz.Document: same page_count/save/close surface,
    but pages are FakePage instances that just record what was drawn."""

    def __init__(self, page_count: int) -> None:
        self.page_count = page_count
        self._pages: dict[int, FakePage] = {}
        self.deleted: list[int] = []
        self.saved_to: str | Path | None = None
        self.closed = False

    def __getitem__(self, index: int) -> FakePage:
        return self._pages.setdefault(index, FakePage())

    def delete_page(self, index: int) -> None:
        self.deleted.append(index)

    def save(self, path, garbage=4, deflate=True) -> None:
        self.saved_to = path

    def close(self) -> None:
        self.closed = True


def test_generate_pdf_premium_layout_stamps_expected_values(monkeypatch, tmp_path):
    fake_doc = FakeDocument(page_count=9)
    monkeypatch.setattr(dg.fitz, "open", lambda *_args, **_kwargs: fake_doc)

    template_path = tmp_path / "template.pdf"
    template_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(dg, "get_pdf_template", lambda: template_path)
    monkeypatch.setattr(dg, "OUTPUT_DIR", tmp_path)
    output_path = tmp_path / "kp_output.pdf"
    monkeypatch.setattr(dg, "PDF_OUTPUT", output_path)

    selected = list(dg.SERVICE_IDS)  # select all -> no pages deleted
    data = {
        "company_name": "ACME LLC",
        "project_deadline": "31.12.2026",
        "selected_services": selected,
        "use_base_prices": True,
    }

    result = dg.generate_pdf(data)

    assert result == str(output_path)
    assert fake_doc.deleted == []  # every service selected, nothing hidden
    assert fake_doc.saved_to == output_path
    assert fake_doc.closed is True

    cover_page = fake_doc[0]
    assert [c for c in cover_page.calls if c[0] == "insert_text"][0][2] == "ACME LLC"

    budget_page = fake_doc[dg.LAYOUT_PREMIUM_V1["budget_page"]]
    texts = _textbox_texts(budget_page)
    total_1m, total_3m, total_6m = dg.calculate_selected_totals(selected)
    assert dg.format_tenge(total_1m) in texts
    assert dg.format_tenge(total_3m) in texts
    assert dg.format_tenge(total_6m) in texts
    assert "31.12.2026" in texts


def test_generate_pdf_deletes_pages_for_unselected_services(monkeypatch, tmp_path):
    fake_doc = FakeDocument(page_count=9)
    monkeypatch.setattr(dg.fitz, "open", lambda *_args, **_kwargs: fake_doc)

    template_path = tmp_path / "template.pdf"
    template_path.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(dg, "get_pdf_template", lambda: template_path)
    monkeypatch.setattr(dg, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(dg, "PDF_OUTPUT", tmp_path / "kp_output.pdf")

    data = {
        "company_name": "ACME LLC",
        "project_deadline": "31.12.2026",
        "selected_services": ["smm_junior"],
        "use_base_prices": True,
    }

    dg.generate_pdf(data)

    # smm_middle (page 6) and ai_assistent (page 8) are not selected
    assert set(fake_doc.deleted) == {6, 8}


def test_generate_pdf_missing_template_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(dg, "get_pdf_template", lambda: tmp_path / "missing.pdf")
    with pytest.raises(FileNotFoundError):
        dg.generate_pdf(_base_payload())
