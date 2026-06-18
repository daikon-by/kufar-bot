from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from kufar_bot.bot.keyboards import main_menu, schedule_menu, weekday_keyboard
from kufar_bot.bot.schedule_nav import is_schedule_menu_button
from kufar_bot.bot.states import ScheduleStates
from kufar_bot.db import repository as repo
from kufar_bot.db.models import User
from kufar_bot.db.session import async_session_factory
from kufar_bot.services.scheduler import get_scheduler

router = Router()
nav_router = Router()

_MENU_FILTER = F.func(lambda message: is_schedule_menu_button(message.text))


@nav_router.message(_MENU_FILTER, flags={"priority": 100})
async def schedule_menu_nav(message: Message, state: FSMContext, db_user: User) -> None:
    await state.clear()
    text = (message.text or "").strip()
    if text == "🕐 Времена":
        await edit_times(message, state)
    elif text == "📅 Дни недели":
        await edit_weekdays(message, state, db_user)
    elif text == "✅ Вкл/Выкл расписание":
        await toggle_schedule(message, db_user)
    elif text == "📋 Текущее":
        await show_schedule_current(message, db_user)
    elif text == "◀️ Назад":
        await message.answer("Главное меню", reply_markup=main_menu(db_user.is_admin))
    elif text == "⏰ Расписание":
        await message.answer("Настройка расписания опросов", reply_markup=schedule_menu())


@router.message(F.text == "🕐 Времена")
async def edit_times(message: Message, state: FSMContext) -> None:
    await state.set_state(ScheduleStates.run_times)
    await message.answer(
        "Введите времена опроса через запятую в формате ЧЧ:ММ\n"
        "Например: 08:00, 14:00, 20:00"
    )


@router.message(ScheduleStates.run_times, ~_MENU_FILTER)
async def save_times(message: Message, state: FSMContext, db_user: User) -> None:
    raw = (message.text or "").replace(";", ",")
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    normalized: list[str] = []
    for part in parts:
        if ":" not in part:
            await message.answer(f"Неверный формат: {part}")
            return
        hour, minute = part.split(":", 1)
        try:
            h, m = int(hour), int(minute)
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
        except ValueError:
            await message.answer(f"Неверное время: {part}")
            return
        normalized.append(f"{h:02d}:{m:02d}")

    async with async_session_factory() as session:
        await repo.update_schedule(session, db_user.telegram_id, run_times=",".join(normalized))
        from kufar_bot.services.scheduler import get_scheduler

        scheduler = get_scheduler()
        if scheduler:
            await scheduler.reload_user(db_user.telegram_id)

    await state.clear()
    await message.answer(f"Времена сохранены: {', '.join(normalized)}", reply_markup=schedule_menu())


@router.message(F.text == "📅 Дни недели")
async def edit_weekdays(message: Message, state: FSMContext, db_user: User) -> None:
    async with async_session_factory() as session:
        schedule = await repo.get_schedule(session, db_user.telegram_id)
    selected = {int(x) for x in schedule.weekdays.split(",") if x.strip().isdigit()}
    await state.update_data(selected_days=list(selected))
    await state.set_state(ScheduleStates.weekdays)
    await message.answer("Выберите дни недели:", reply_markup=weekday_keyboard(selected))


@router.callback_query(ScheduleStates.weekdays, F.data.startswith("sched:wd:"))
async def toggle_weekday(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":")[-1]
    if action == "save":
        data = await state.get_data()
        days = sorted(set(data.get("selected_days", [])))
        if not days:
            await callback.answer("Выберите хотя бы один день", show_alert=True)
            return
        user_id = callback.from_user.id
        async with async_session_factory() as session:
            await repo.update_schedule(session, user_id, weekdays=",".join(str(d) for d in days))
            scheduler = get_scheduler()
            if scheduler:
                await scheduler.reload_user(user_id)
        await state.clear()
        await callback.message.edit_text(f"Дни сохранены: {days}")
        await callback.answer()
        return

    day = int(action)
    data = await state.get_data()
    selected = set(data.get("selected_days", []))
    if day in selected:
        selected.remove(day)
    else:
        selected.add(day)
    await state.update_data(selected_days=list(selected))
    await callback.message.edit_reply_markup(reply_markup=weekday_keyboard(selected))
    await callback.answer()


@router.message(F.text == "📋 Текущее")
async def show_schedule_current(message: Message, db_user: User) -> None:
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
        f"Часовой пояс: {schedule.timezone}",
        reply_markup=schedule_menu(),
    )


@router.message(F.text == "✅ Вкл/Выкл расписание")
async def toggle_schedule(message: Message, db_user: User) -> None:
    async with async_session_factory() as session:
        schedule = await repo.get_schedule(session, db_user.telegram_id)
        new_value = not schedule.is_enabled
        await repo.update_schedule(session, db_user.telegram_id, is_enabled=new_value)
        scheduler = get_scheduler()
        if scheduler:
            await scheduler.reload_user(db_user.telegram_id)
    status = "включено" if new_value else "выключено"
    await message.answer(f"Расписание {status}", reply_markup=schedule_menu())
