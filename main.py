import asyncio
import logging
import os

from bot_setup import create_bot_and_dispatcher
from config import OUTPUT_DIR, get_pdf_template

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_template = get_pdf_template()
    if not pdf_template.exists():
        logger.warning("PDF-шаблон не найден: %s", pdf_template)

    bot, dp = create_bot_and_dispatcher()

    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Бот успешно запущен (polling). Шаблон: %s", pdf_template)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
