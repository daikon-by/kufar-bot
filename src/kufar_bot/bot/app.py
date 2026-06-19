from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from kufar_bot.bot.handlers import admin, callbacks, favorites, groups, minus, schedule, start
from kufar_bot.bot.handlers.groups import nav_router as groups_nav_router
from kufar_bot.bot.handlers.schedule import nav_router as schedule_nav_router
from kufar_bot.bot.middlewares import AuthMiddleware
from kufar_bot.services.scheduler import PollScheduler


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Навигация групп — выше FSM, иначе кнопки меню попадают в ввод ссылок
    dp.include_router(groups_nav_router)
    dp.include_router(schedule_nav_router)
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(groups.router)
    dp.include_router(minus.router)
    dp.include_router(favorites.router)
    dp.include_router(schedule.router)
    dp.include_router(callbacks.router)
    return dp


async def run_bot(bot: Bot, scheduler: PollScheduler) -> None:
    dp = create_dispatcher()
    await dp.start_polling(bot)
