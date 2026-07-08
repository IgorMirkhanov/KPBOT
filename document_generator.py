import logging
import os
import shutil
import urllib.request
from pathlib import Path

import fitz
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import (
    ARIAL_FONT_PATH,
    BUNDLED_FONT_CANDIDATES,
    FONTS_DIR,
    OUTPUT_DIR,
    PDF_OUTPUT,
    _WIN_ARIAL,
    get_pdf_template,
)

logger = logging.getLogger(__name__)

FONT_NAME = "Arial"
TEXT_COLOR_DARK_BG = (1.0, 1.0, 1.0)
TEXT_COLOR_LIGHT_BG = (0.1, 0.1, 0.1)
TABLE_BG_DARK = (0.066, 0.066, 0.066)
TABLE_BG_LIGHT = (1.0, 1.0, 1.0)

_FONTS_REGISTERED = False

BASE_PRICES: dict[str, dict] = {
    "smm_junior": {
        "name": "SMM Junior+Таргет",
        "1m": "850 000 тг",
        "3m": "2 295 000 тг",
        "6m": "4 335 000 тг",
        "val_1m": 850_000,
        "val_3m": 2_295_000,
        "val_6m": 4_335_000,
    },
    "smm_middle": {
        "name": "SMM Middle+Таргет",
        "1m": "950 000 тг",
        "3m": "2 565 000 тг",
        "6m": "4 845 000 тг",
        "val_1m": 950_000,
        "val_3m": 2_565_000,
        "val_6m": 4_845_000,
    },
    "target_insta": {
        "name": "Таргет Insta",
        "1m": "400 000 тг",
        "3m": "1 080 000 тг",
        "6m": "2 040 000 тг",
        "val_1m": 400_000,
        "val_3m": 1_080_000,
        "val_6m": 2_040_000,
    },
    "context": {
        "name": "Контекстная реклама",
        "1m": "165 000 тг",
        "3m": "445 500 тг",
        "6m": "841 500 тг",
        "val_1m": 165_000,
        "val_3m": 445_500,
        "val_6m": 841_500,
    },
    "seo": {
        "name": "SEO оптимизация",
        "1m": "считается по смете",
        "3m": "—",
        "6m": "—",
        "val_1m": 0,
        "val_3m": 0,
        "val_6m": 0,
    },
    "website": {
        "name": "Разработка сайта",
        "1m": "от 1 050 000 тг",
        "3m": "—",
        "6m": "—",
        "val_1m": 1_050_000,
        "val_3m": 0,
        "val_6m": 0,
    },
    "ai_assistent": {
        "name": "ИИ-ассистент",
        "1m": "250 000 разработка",
        "3m": "125 000 тг/мес (обсл.)",
        "6m": "125 000 тг/мес (обсл.)",
        "val_1m": 250_000,
        "val_3m": 125_000,
        "val_6m": 125_000,
    },
}

SERVICE_IDS: tuple[str, ...] = tuple(BASE_PRICES.keys())

SERVICE_CATALOG: dict[str, dict[str, str]] = {
    service_id: {"label": meta["name"]} for service_id, meta in BASE_PRICES.items()
}

# Premium — budget page index 7, тёмная таблица (X 45–585)
LAYOUT_PREMIUM_V1 = {
    "name": "premium_v1",
    "budget_page": 7,
    "cover_company": (72.0, 300.0),
    "cover_fontsize": 22.0,
    "cover_text_color": TEXT_COLOR_DARK_BG,
    "service_pages": {
        "smm_junior": [5],
        "smm_middle": [6],
        "ai_assistent": [8],
    },
    "budget": {
        "mask_fill": TABLE_BG_DARK,
        "text_color": TEXT_COLOR_DARK_BG,
        "service_rows": {
            "smm_junior": (45.0, 280.0, 585.0, 310.0),
            "smm_middle": (45.0, 315.0, 585.0, 345.0),
            "target_insta": (45.0, 350.0, 585.0, 380.0),
            "context": (45.0, 385.0, 585.0, 415.0),
            "seo": (45.0, 420.0, 585.0, 450.0),
            "website": (45.0, 455.0, 585.0, 485.0),
            "ai_assistent": (45.0, 490.0, 585.0, 520.0),
        },
        "total_row": (45.0, 525.0, 585.0, 555.0),
        "deadline_row": (45.0, 560.0, 585.0, 590.0),
        "total_fontsize": 10.0,
        "meta_fontsize": 10.0,
        "cols": {
            1: {"x0": 50.0, "x1": 240.0, "align": fitz.TEXT_ALIGN_LEFT},
            2: {"x0": 250.0, "x1": 350.0, "align": fitz.TEXT_ALIGN_RIGHT},
            3: {"x0": 360.0, "x1": 470.0, "align": fitz.TEXT_ALIGN_RIGHT},
            4: {"x0": 480.0, "x1": 580.0, "align": fitz.TEXT_ALIGN_RIGHT},
        },
    },
}

# Legacy 21-page — budget page index 18, светлая таблица
LAYOUT_LEGACY_V1 = {
    "name": "legacy_v1",
    "budget_page": 18,
    "cover_company": (72.0, 290.0),
    "cover_fontsize": 24.0,
    "cover_text_color": TEXT_COLOR_LIGHT_BG,
    "service_pages": {
        "smm_junior": [8],
        "smm_middle": [9],
        "target_insta": [10, 11],
        "context": [12, 13],
        "seo": [14, 15],
        "website": [16, 17],
        "ai_assistent": [19],
    },
    "budget": {
        "mask_fill": TABLE_BG_LIGHT,
        "text_color": TEXT_COLOR_LIGHT_BG,
        "service_rows": {
            "smm_junior": (12.0, 128.0, 708.0, 157.0),
            "smm_middle": (12.0, 157.0, 708.0, 192.0),
            "target_insta": (12.0, 192.0, 708.0, 222.0),
            "context": (12.0, 222.0, 708.0, 252.0),
            "seo": (12.0, 252.0, 708.0, 282.0),
            "website": (12.0, 282.0, 708.0, 342.0),
            "ai_assistent": (12.0, 342.0, 708.0, 392.0),
        },
        "total_row": (12.0, 392.0, 708.0, 422.0),
        "deadline_row": (12.0, 422.0, 708.0, 452.0),
        "total_fontsize": 11.0,
        "meta_fontsize": 10.0,
        "cols": {
            1: {"x0": 15.0, "x1": 185.0, "align": fitz.TEXT_ALIGN_LEFT},
            2: {"x0": 191.0, "x1": 358.0, "align": fitz.TEXT_ALIGN_RIGHT},
            3: {"x0": 370.0, "x1": 530.0, "align": fitz.TEXT_ALIGN_RIGHT},
            4: {"x0": 544.0, "x1": 708.0, "align": fitz.TEXT_ALIGN_RIGHT},
        },
    },
}


def _arial_source_candidates() -> list[Path]:
    candidates = list(BUNDLED_FONT_CANDIDATES) + [
        _WIN_ARIAL,
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"),
    ]
    return [p for p in candidates if p.exists()]


def _download_fallback_font() -> None:
    """Download DejaVu Sans as fallback Cyrillic font."""
    url = (
        "https://github.com/dejavu-fonts/dejavu-fonts/raw/"
        "version_2_37/ttf/DejaVuSans.ttf"
    )
    logger.info("Downloading fallback font DejaVu Sans -> %s", ARIAL_FONT_PATH)
    urllib.request.urlretrieve(url, ARIAL_FONT_PATH)


def ensure_arial_font() -> Path:
    """Copy bundled font into writable FONTS_DIR (required on Vercel /tmp)."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    if ARIAL_FONT_PATH.exists() and ARIAL_FONT_PATH.stat().st_size > 0:
        return ARIAL_FONT_PATH

    for source in _arial_source_candidates():
        shutil.copy2(source, ARIAL_FONT_PATH)
        logger.info("Font copied to %s from %s", ARIAL_FONT_PATH, source)
        return ARIAL_FONT_PATH

    try:
        _download_fallback_font()
        return ARIAL_FONT_PATH
    except OSError as exc:
        raise FileNotFoundError(
            "Cyrillic font not found. Bundle assets/fonts/Arial.ttf in the project."
        ) from exc


def register_arial_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    font_path = ensure_arial_font()
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))
    _FONTS_REGISTERED = True


def sanitize_price_digits(raw_price: str | int | float) -> int:
    if isinstance(raw_price, bool):
        raise ValueError("Цена должна быть положительным числом")
    if isinstance(raw_price, int):
        value = raw_price
    elif isinstance(raw_price, float):
        value = int(round(raw_price))
    else:
        digits = "".join(c for c in str(raw_price) if c.isdigit())
        if not digits:
            raise ValueError("Цена должна содержать число")
        value = int(digits)
    if value <= 0:
        raise ValueError("Цена должна быть положительным числом")
    return value


def format_user_price(raw_price: str) -> str:
    return format_tenge(sanitize_price_digits(raw_price))


def format_tenge(amount: int) -> str:
    if amount <= 0:
        return "—"
    return f"{amount:,}".replace(",", " ") + " тг"


def calculate_selected_totals(selected_services: list[str]) -> tuple[int, int, int]:
    total_1m = sum(BASE_PRICES[s]["val_1m"] for s in selected_services)
    total_3m = sum(BASE_PRICES[s]["val_3m"] for s in selected_services)
    total_6m = sum(BASE_PRICES[s]["val_6m"] for s in selected_services)
    return total_1m, total_3m, total_6m


def calculate_custom_packages(custom_price: int) -> tuple[int, int, int]:
    price_1m = custom_price
    price_3m = int(round(price_1m * 3 * 0.9))
    price_6m = int(round(price_1m * 6 * 0.85))
    return price_1m, price_3m, price_6m


def validate_pdf_data(data: dict) -> dict:
    required_keys = (
        "company_name",
        "project_deadline",
        "selected_services",
        "use_base_prices",
    )
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise ValueError(f"Отсутствуют обязательные поля для PDF: {', '.join(missing)}")

    selected_services: list[str] = list(data["selected_services"])
    if not selected_services:
        raise ValueError("Не выбрано ни одной услуги")

    unknown = [sid for sid in selected_services if sid not in BASE_PRICES]
    if unknown:
        raise ValueError(f"Неизвестные услуги: {', '.join(unknown)}")

    company_name = str(data["company_name"]).strip()
    project_deadline = str(data["project_deadline"]).strip()
    use_base_prices = bool(data["use_base_prices"])

    if not company_name:
        raise ValueError("Не указано название компании")
    if not project_deadline:
        raise ValueError("Не указан срок действия КП / дата запуска")

    payload: dict = {
        "company_name": company_name,
        "project_deadline": project_deadline,
        "selected_services": selected_services,
        "use_base_prices": use_base_prices,
    }

    if use_base_prices:
        total_1m, total_3m, total_6m = calculate_selected_totals(selected_services)
    else:
        if data.get("custom_price") is None:
            raise ValueError("Не указана кастомная стоимость")
        custom_price = sanitize_price_digits(data["custom_price"])
        total_1m, total_3m, total_6m = calculate_custom_packages(custom_price)
        payload["custom_price"] = custom_price

    payload.update({"total_1m": total_1m, "total_3m": total_3m, "total_6m": total_6m})
    return payload


def _resolve_layout(page_count: int) -> dict:
    if page_count == 9:
        return LAYOUT_PREMIUM_V1
    if page_count >= 19:
        return LAYOUT_LEGACY_V1
    raise ValueError(
        f"Неподдерживаемая структура PDF ({page_count} стр.). "
        f"Ожидается 9 (premium) или 21 (legacy) страниц."
    )


def _ensure_page_font(page: fitz.Page) -> None:
    font_path = str(ensure_arial_font())
    registered = {f[0] for f in page.get_fonts()}
    if FONT_NAME not in registered:
        page.insert_font(fontname=FONT_NAME, fontfile=font_path)


def _rect_from_tuple(coords: tuple[float, float, float, float]) -> fitz.Rect:
    return fitz.Rect(*coords)


def _cover_rect(page: fitz.Page, rect: fitz.Rect, bg_color: tuple[float, float, float]) -> None:
    """Маскирует область сплошным прямоугольником цвета фона таблицы."""
    page.draw_rect(rect, color=bg_color, fill=bg_color, overlay=True)


def _col_rect(budget: dict, col: int, row_coords: tuple[float, float, float, float]) -> fitz.Rect:
    _, y0, _, y1 = row_coords
    col_cfg = budget["cols"][col]
    return fitz.Rect(col_cfg["x0"], y0, col_cfg["x1"], y1)


def _insert_textbox_cell(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    fontsize: float,
    color: tuple[float, float, float],
    align: int,
) -> None:
    _ensure_page_font(page)
    overflow = page.insert_textbox(
        rect,
        text,
        fontname=FONT_NAME,
        fontsize=fontsize,
        color=color,
        align=align,
    )
    if overflow < 0:
        logger.warning("Текст не поместился в ячейку %s: %s", rect, text[:60])


def _mask_service_rows(
    page: fitz.Page,
    selected_services: list[str],
    use_base_prices: bool,
    budget: dict,
) -> None:
    bg_color = budget["mask_fill"]
    selected_set = set(selected_services)

    for service_id in SERVICE_IDS:
        row = _rect_from_tuple(budget["service_rows"][service_id])
        hide_row = (not use_base_prices) or (service_id not in selected_set)
        if hide_row:
            _cover_rect(page, row, bg_color)


def _write_total_row(
    page: fitz.Page,
    budget: dict,
    total_1m: int,
    total_3m: int,
    total_6m: int,
) -> None:
    row_coords = budget["total_row"]
    bg_color = budget["mask_fill"]
    color = budget["text_color"]
    fontsize = budget["total_fontsize"]
    cols = budget["cols"]

    _cover_rect(page, _rect_from_tuple(row_coords), bg_color)

    _insert_textbox_cell(
        page, _col_rect(budget, 1, row_coords), "ИТОГО", fontsize, color, cols[1]["align"]
    )
    _insert_textbox_cell(
        page,
        _col_rect(budget, 2, row_coords),
        format_tenge(total_1m),
        fontsize,
        color,
        cols[2]["align"],
    )
    _insert_textbox_cell(
        page,
        _col_rect(budget, 3, row_coords),
        format_tenge(total_3m),
        fontsize,
        color,
        cols[3]["align"],
    )
    _insert_textbox_cell(
        page,
        _col_rect(budget, 4, row_coords),
        format_tenge(total_6m),
        fontsize,
        color,
        cols[4]["align"],
    )


def _write_deadline_row(page: fitz.Page, budget: dict, project_deadline: str) -> None:
    row_coords = budget["deadline_row"]
    bg_color = budget["mask_fill"]
    color = budget["text_color"]
    fontsize = budget["meta_fontsize"]
    cols = budget["cols"]

    _cover_rect(page, _rect_from_tuple(row_coords), bg_color)

    _insert_textbox_cell(
        page,
        _col_rect(budget, 1, row_coords),
        "Срок / дата запуска:",
        fontsize,
        color,
        cols[1]["align"],
    )
    _insert_textbox_cell(
        page,
        _col_rect(budget, 2, row_coords),
        project_deadline,
        fontsize,
        color,
        cols[2]["align"],
    )


def _pages_to_delete(selected_services: list[str], layout: dict) -> list[int]:
    pages: set[int] = set()
    for service_id, page_list in layout["service_pages"].items():
        if service_id not in selected_services:
            pages.update(page_list)
    return sorted(pages, reverse=True)


def _budget_page_after_deletions(original_budget_page: int, deleted_pages: list[int]) -> int:
    shift = sum(1 for page in deleted_pages if page < original_budget_page)
    return original_budget_page - shift


def _inject_cover(page: fitz.Page, company_name: str, layout: dict) -> None:
    x, y = layout["cover_company"]
    fontsize = layout["cover_fontsize"]
    color = layout.get("cover_text_color", TEXT_COLOR_LIGHT_BG)
    _ensure_page_font(page)
    page.insert_text((x, y), company_name, fontname=FONT_NAME, fontsize=fontsize, color=color)


def _inject_budget(
    page: fitz.Page,
    selected_services: list[str],
    use_base_prices: bool,
    total_1m: int,
    total_3m: int,
    total_6m: int,
    project_deadline: str,
    layout: dict,
) -> None:
    budget = layout["budget"]
    _mask_service_rows(page, selected_services, use_base_prices, budget)
    _write_total_row(page, budget, total_1m, total_3m, total_6m)
    _write_deadline_row(page, budget, project_deadline)


def generate_pdf(data: dict) -> str:
    """
    CPU-bound редактирование PDF через PyMuPDF.
    Вызывать из хэндлера: await asyncio.to_thread(generate_pdf, data)
    """
    register_arial_fonts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not get_pdf_template().exists():
        raise FileNotFoundError(
            f"PDF-шаблон не найден: {get_pdf_template()}. "
            "Поместите commercial_proposal.pdf в папку templates/."
        )

    payload = validate_pdf_data(data)
    doc = fitz.open(get_pdf_template())
    layout = _resolve_layout(doc.page_count)

    pages_to_delete = _pages_to_delete(payload["selected_services"], layout)
    for page_number in pages_to_delete:
        doc.delete_page(page_number)

    budget_page = _budget_page_after_deletions(layout["budget_page"], pages_to_delete)

    _inject_cover(doc[0], payload["company_name"], layout)
    _inject_budget(
        doc[budget_page],
        payload["selected_services"],
        payload["use_base_prices"],
        payload["total_1m"],
        payload["total_3m"],
        payload["total_6m"],
        payload["project_deadline"],
        layout,
    )

    doc.save(PDF_OUTPUT, garbage=4, deflate=True)
    doc.close()

    logger.info(
        "PDF: %s | layout=%s | base=%s | итого=%s/%s/%s | услуги=%s",
        PDF_OUTPUT,
        layout["name"],
        payload["use_base_prices"],
        payload["total_1m"],
        payload["total_3m"],
        payload["total_6m"],
        payload["selected_services"],
    )
    return str(PDF_OUTPUT)
