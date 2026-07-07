import logging
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

if os.getenv("VERCEL"):
    OUTPUT_DIR: Path = Path("/tmp/kpbot/output")
    FONTS_DIR: Path = Path("/tmp/kpbot/fonts")
else:
    OUTPUT_DIR = BASE_DIR / "output"
    FONTS_DIR = BASE_DIR / "fonts"

PDF_TEMPLATE: Path = BASE_DIR / "templates" / "commercial_proposal.pdf"
_PDF_LEGACY: Path = BASE_DIR / "Коммерческое_Предложение.pdf"

PDF_OUTPUT: Path = OUTPUT_DIR / "kp_output.pdf"
ARIAL_FONT_PATH: Path = FONTS_DIR / "Arial.ttf"

_WIN_ARIAL: Path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"

WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
REDIS_URL: str = os.getenv("REDIS_URL", "")
UPSTASH_REDIS_REST_URL: str = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_REDIS_REST_TOKEN: str = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")


def get_pdf_template() -> Path:
    if PDF_TEMPLATE.exists():
        return PDF_TEMPLATE
    if _PDF_LEGACY.exists():
        return _PDF_LEGACY
    return PDF_TEMPLATE


def get_redis_url() -> str:
    for key in ("REDIS_URL", "UPSTASH_REDIS_URL", "KV_URL"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return REDIS_URL.strip()


def get_upstash_rest_credentials() -> tuple[str, str]:
    url = UPSTASH_REDIS_REST_URL.strip() or os.getenv("KV_REST_API_URL", "").strip()
    token = UPSTASH_REDIS_REST_TOKEN.strip() or os.getenv("KV_REST_API_TOKEN", "").strip()
    return url, token
