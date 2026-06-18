import asyncio
import sys
from pathlib import Path

import structlog
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from kufar_bot.bot.app import run_bot
from kufar_bot.config import settings
from kufar_bot.db.repository import ensure_admins
from kufar_bot.db.session import async_session_factory, init_db
from kufar_bot.logging_setup import LOG_FILE, setup_logging
from kufar_bot.services.scheduler import PollScheduler, set_scheduler


async def async_main() -> None:
    setup_logging()
    log = structlog.get_logger()

    if not settings.is_configured:
        log.error("config_missing", hint="BOT_TOKEN и ADMIN_IDS в .env")
        sys.exit(1)

    Path("data").mkdir(exist_ok=True)
    await init_db()

    async with async_session_factory() as session:
        await ensure_admins(session)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    scheduler = PollScheduler(bot)
    set_scheduler(scheduler)
    await scheduler.start()

    log.info("bot_started", admins=settings.admin_id_list, log_file=str(LOG_FILE))
    try:
        await run_bot(bot, scheduler)
    finally:
        await scheduler.shutdown()
        await bot.session.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
