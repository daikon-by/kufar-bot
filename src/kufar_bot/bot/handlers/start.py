import asyncio

import structlog
from aiogram import F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from kufar_bot.bot.keyboards import groups_menu, main_menu, minus_menu, poll_stop_keyboard, schedule_menu
from kufar_bot.config import settings
from kufar_bot.db import repository as repo
from kufar_bot.db.models import User
from kufar_bot.db.session import async_session_factory
from kufar_bot.services.poll_cancel import poll_cancel

router = Router()
log = structlog.get_logger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User) -> None:
    if not repo.user_has_access(db_user):
        await message.answer(
            f"Привет! Это бот мониторинга Kufar.\n\n"
            f"Доступ по приглашению. Напишите администратору @{settings.admin_username}\n"
            f"Ваш Telegram ID: <code>{message.from_user.id}</code>",
            parse_mode="HTML",
        )
        return
    await message.answer(
        "Бот мониторинга Kufar готов.\n"
        "Добавьте группы поиска, минус-слова и настройте расписание.",
        reply_markup=main_menu(db_user.is_admin),
    )


@router.message(F.text == "◀️ Назад")
async def go_back(message: Message, db_user: User) -> None:
    await message.answer("Главное меню", reply_markup=main_menu(db_user.is_admin))


@router.message(F.text == "📁 Группы")
async def open_groups(message: Message) -> None:
    await message.answer("Управление группами поиска", reply_markup=groups_menu())


@router.message(F.text == "⛔ Минус-слова")
async def open_minus(message: Message) -> None:
    await message.answer("Минус-фразы (подстрока, без учёта регистра)", reply_markup=minus_menu())


@router.message(F.text == "⏰ Расписание")
async def open_schedule(message: Message) -> None:
    await message.answer("Настройка расписания опросов", reply_markup=schedule_menu())


async def _run_manual_poll(bot, user_id: int, stop_message_id: int | None) -> None:
    from kufar_bot.services.poller import poll_user
    from kufar_bot.services.telegram_retry import with_flood_retry

    try:
        async with async_session_factory() as session:
            await poll_user(session, bot, user_id, manual=True)
    except TelegramRetryAfter:
        log.warning("manual_poll_flood", user_id=user_id)
    except Exception:
        log.exception("manual_poll_failed", user_id=user_id)
        try:
            await with_flood_retry(
                "manual_poll_error",
                lambda: bot.send_message(user_id, "Ошибка опроса. Подробности: data/kufar_bot.log"),
            )
        except Exception:
            pass
    finally:
        poll_cancel.clear(user_id)
        if stop_message_id is not None:
            try:
                await bot.edit_message_reply_markup(chat_id=user_id, message_id=stop_message_id)
            except Exception:
                pass


@router.message(F.text == "▶️ Опрос сейчас")
async def manual_poll(message: Message, db_user: User) -> None:
    user_id = db_user.telegram_id
    if poll_cancel.is_active(user_id):
        await message.answer(
            "Опрос уже идёт. Нажмите «⏹ Остановить опрос».",
            reply_markup=poll_stop_keyboard(),
        )
        return

    log.info("manual_poll_requested", user_id=user_id)
    poll_cancel.start(user_id)
    stop_msg = await message.answer(
        "Опрос запущен. Можно остановить кнопкой ниже или «⏹ Остановить опрос» в меню.",
        reply_markup=poll_stop_keyboard(),
    )
    asyncio.create_task(_run_manual_poll(message.bot, user_id, stop_msg.message_id))


@router.message(F.text == "⏹ Остановить опрос")
async def poll_stop_message(message: Message, db_user: User) -> None:
    if poll_cancel.request_cancel(db_user.telegram_id):
        await message.answer("⏹ Останавливаю опрос…")
    else:
        await message.answer("Сейчас опрос не выполняется.")


@router.callback_query(F.data == "poll:stop")
async def poll_stop_callback(callback: CallbackQuery, db_user: User) -> None:
    if poll_cancel.request_cancel(db_user.telegram_id):
        await callback.answer("Останавливаю опрос…")
        if callback.message is not None:
            try:
                await callback.message.edit_text("⏹ Останавливаю опрос…")
            except Exception:
                pass
    else:
        await callback.answer("Сейчас опрос не выполняется", show_alert=True)


@router.message(F.text == "📋 Текущее")
async def show_schedule(message: Message, db_user: User) -> None:
    async with async_session_factory() as session:
        schedule = await repo.get_schedule(session, db_user.telegram_id)
    days = [int(x) for x in schedule.weekdays.split(",") if x.strip().isdigit()]
    day_labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    selected = ", ".join(day_labels[i] for i in days if 0 <= i <= 6)
    await message.answer(
        f"Расписание:\n"
        f"Статус: {'включено' if schedule.is_enabled else 'выключено'}\n"
        f"Дни: {selected or 'не заданы'}\n"
        f"Времена: {schedule.run_times}\n"
        f"Часовой пояс: {schedule.timezone}"
    )


@router.message(Command("help"))
async def cmd_help(message: Message, db_user: User) -> None:
    text = (
        "/start — главное меню\n"
        "/help — справка\n"
        "Группы — ссылки отборов Kufar по разделам и регионам\n"
        "Минус-слова — глобальные фильтры по подстроке\n"
        "Расписание — дни недели и времена опроса\n"
        "Избранное — отслеживание цены при каждом опросе\n"
        "⏹ Остановить опрос — прервать текущую рассылку объявлений"
    )
    if db_user.is_admin:
        text += (
            "\n\nАдмин:\n"
            "/allow <id> [дней] — выдать доступ\n"
            "/revoke <id> — отозвать доступ\n"
            "/users — список пользователей"
        )
    await message.answer(text)
