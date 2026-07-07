import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OUTPUT_DIR: Path = BASE_DIR / "output"
FONTS_DIR: Path = BASE_DIR / "fonts"

# ASCII-путь для кросс-платформенного деплоя (Vercel/Linux)
PDF_TEMPLATE: Path = BASE_DIR / "templates" / "commercial_proposal.pdf"
# Локальный fallback с кириллическим именем
_PDF_LEGACY: Path = BASE_DIR / "Коммерческое_Предложение.pdf"

PDF_OUTPUT: Path = OUTPUT_DIR / "kp_output.pdf"
ARIAL_FONT_PATH: Path = FONTS_DIR / "Arial.ttf"

_WIN_ARIAL: Path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"

WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
REDIS_URL: str = os.getenv("REDIS_URL", "")


def get_pdf_template() -> Path:
    if PDF_TEMPLATE.exists():
        return PDF_TEMPLATE
    if _PDF_LEGACY.exists():
        return _PDF_LEGACY
    return PDF_TEMPLATE
