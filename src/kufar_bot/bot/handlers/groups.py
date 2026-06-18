import html
import json

import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from kufar_bot.bot.groups_nav import is_groups_menu_button
from kufar_bot.bot.keyboards import group_actions, group_url_actions, groups_menu, main_menu
from kufar_bot.bot.states import AddGroupStates, AddGroupUrlStates
from kufar_bot.db import repository as repo
from kufar_bot.db.models import User
from kufar_bot.db.session import async_session_factory
from kufar_bot.kufar.client import KufarClient
from kufar_bot.kufar.url_parser import is_kufar_url

router = Router()
nav_router = Router()
log = structlog.get_logger(__name__)

_MENU_FILTER = F.func(lambda message: is_groups_menu_button(message.text))


def _format_group_urls(group) -> str:
    lines = [
        f"<b>{group.name}</b> (id {group.id})",
        f"Раздел: {group.section_label or '—'} · Регион: {group.region_label or '—'}",
    ]
    if not group.urls:
        lines.append("Ссылок нет.")
        return "\n".join(lines)
    for idx, item in enumerate(group.urls, start=1):
        lines.append(f'{idx}. <a href="{item.url}">{item.url}</a>')
    return "\n".join(lines)


async def _send_group_urls(message: Message, group) -> None:
    await message.answer(
        _format_group_urls(group),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=group_actions(group.id),
    )


async def _send_all_urls(message: Message, db_user: User) -> None:
    async with async_session_factory() as session:
        groups = await repo.get_user_groups(session, db_user.telegram_id)
    if not groups:
        await message.answer("Групп и ссылок пока нет.", reply_markup=groups_menu())
        return

    total = sum(len(g.urls) for g in groups)
    if total == 0:
        await message.answer("Группы есть, но ссылки не добавлены.", reply_markup=groups_menu())
        return

    for group in groups:
        if not group.urls:
            continue
        await _send_group_urls(message, group)


@nav_router.message(_MENU_FILTER, flags={"priority": 100})
async def groups_menu_nav(message: Message, state: FSMContext, db_user: User) -> None:
    """Всегда первым: кнопки меню групп, в т.ч. во время FSM."""
    await state.clear()
    text = (message.text or "").strip()
    log.info("groups_menu_nav", user_id=db_user.telegram_id, button=text)
    if text == "📋 Список групп":
        await list_groups(message, state, db_user)
    elif text == "🔗 Мои ссылки":
        await list_all_urls(message, state, db_user)
    elif text == "➕ Добавить группу":
        await add_group_start(message, state)
    elif text == "◀️ Назад":
        await message.answer("Главное меню", reply_markup=main_menu(db_user.is_admin))
    elif text == "📁 Группы":
        await message.answer("Управление группами поиска", reply_markup=groups_menu())


@router.message(AddGroupStates.name, ~_MENU_FILTER)
async def add_group_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AddGroupStates.section_label)
    await message.answer("Раздел (например: Сад и огород). Можно «-» чтобы пропустить.")


@router.message(AddGroupStates.section_label, ~_MENU_FILTER)
async def add_group_section(message: Message, state: FSMContext) -> None:
    value = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(section_label=value)
    await state.set_state(AddGroupStates.region_label)
    await message.answer("Регион (например: Бобруйский район). Можно «-» чтобы пропустить.")


@router.message(AddGroupStates.region_label, ~_MENU_FILTER)
async def add_group_region(message: Message, state: FSMContext) -> None:
    value = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(region_label=value)
    await state.set_state(AddGroupStates.urls)
    await message.answer(
        "Отправьте одну или несколько ссылок Kufar (каждая с новой строки).\n"
        "Когда закончите — /done\n"
        "Отмена — /cancel"
    )


@router.message(AddGroupStates.urls, F.text == "/done")
async def add_group_done(message: Message, state: FSMContext, db_user: User) -> None:
    data = await state.get_data()
    urls: list[str] = data.get("urls", [])
    if not urls:
        await message.answer("Нужна хотя бы одна ссылка. Отправьте URL и снова /done")
        return

    async with async_session_factory() as session:
        group = await repo.create_group(
            session,
            db_user.telegram_id,
            data["name"],
            data.get("section_label", ""),
            data.get("region_label", ""),
        )
        async with KufarClient() as client:
            for url in urls:
                api_query = await client.resolve_search_query(url)
                log.info(
                    "group_url_added",
                    user_id=db_user.telegram_id,
                    group_id=group.id,
                    url=url,
                    api_query=api_query,
                )
                await repo.add_group_url(session, group.id, url, json.dumps(api_query, ensure_ascii=False))

    await state.clear()
    await message.answer(
        f"Группа «{group.name}» создана. Ссылок: {len(urls)}.",
        reply_markup=groups_menu(),
    )


@router.message(AddGroupStates.urls, ~_MENU_FILTER, F.text != "/done", F.text != "/cancel")
async def add_group_urls(message: Message, state: FSMContext) -> None:
    lines = [line.strip() for line in (message.text or "").splitlines() if line.strip()]
    valid: list[str] = []
    for line in lines:
        if not is_kufar_url(line):
            await message.answer(f"Пропущена невалидная ссылка:\n{line}")
            continue
        valid.append(line)
    if not valid:
        await message.answer("Не найдено валидных ссылок Kufar (/l/...).")
        return
    data = await state.get_data()
    urls = data.get("urls", [])
    urls.extend(valid)
    await state.update_data(urls=urls)
    await message.answer(f"Добавлено ссылок: {len(valid)}. Всего: {len(urls)}. Ещё ссылки или /done")


@router.message(AddGroupStates.urls, F.text == "/cancel")
async def add_group_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добавление группы отменено.", reply_markup=groups_menu())


@router.message(F.text == "➕ Добавить группу")
async def add_group_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AddGroupStates.name)
    await message.answer("Введите название группы (например: Сад)")


@router.message(F.text == "📋 Список групп")
async def list_groups(message: Message, state: FSMContext, db_user: User) -> None:
    await state.clear()
    async with async_session_factory() as session:
        groups = await repo.get_user_groups(session, db_user.telegram_id)
    if not groups:
        await message.answer("Групп пока нет.", reply_markup=groups_menu())
        return
    for group in groups:
        text = (
            f"<b>{group.name}</b> (id {group.id})\n"
            f"Раздел: {group.section_label or '—'}\n"
            f"Регион: {group.region_label or '—'}\n"
            f"Ссылок: {len(group.urls)}"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=group_actions(group.id))


@router.message(F.text == "🔗 Мои ссылки")
async def list_all_urls(message: Message, state: FSMContext, db_user: User) -> None:
    await state.clear()
    log.info("list_all_urls", user_id=db_user.telegram_id)
    await _send_all_urls(message, db_user)


@router.callback_query(F.data.startswith("group:urls:"))
async def list_group_urls_callback(callback: CallbackQuery, db_user: User) -> None:
    group_id = int(callback.data.split(":")[-1])
    async with async_session_factory() as session:
        group = await repo.get_group(session, group_id, db_user.telegram_id)
    if group is None:
        await callback.answer("Группа не найдена", show_alert=True)
        return
    await callback.message.answer(
        _format_group_urls(group),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    for item in group.urls:
        await callback.message.answer(
            f"#{item.id}\n{item.url}",
            reply_markup=group_url_actions(item.id, group.id),
            disable_web_page_preview=True,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("group:url:del:"))
async def delete_group_url_callback(callback: CallbackQuery, db_user: User) -> None:
    parts = callback.data.split(":")
    url_id = int(parts[3])
    group_id = int(parts[4])
    async with async_session_factory() as session:
        ok = await repo.delete_group_url(session, url_id, db_user.telegram_id)
        group = await repo.get_group(session, group_id, db_user.telegram_id)
    if not ok:
        await callback.answer("Ссылка не найдена", show_alert=True)
        return
    await callback.message.edit_text(f"🗑 Ссылка #{url_id} удалена")
    await callback.answer("Удалено")
    if group and group.urls:
        await callback.message.answer(
            f"Осталось ссылок в «{group.name}»: {len(group.urls)}",
            reply_markup=group_actions(group.id),
        )


@router.callback_query(F.data.startswith("group:url:reset:"))
async def reset_url_poll_callback(callback: CallbackQuery, db_user: User) -> None:
    parts = callback.data.split(":")
    url_id = int(parts[3])
    group_id = int(parts[4])
    async with async_session_factory() as session:
        ok = await repo.reset_search_url_poll_state(session, url_id, db_user.telegram_id)
    if not ok:
        await callback.answer("Ссылка не найдена", show_alert=True)
        return
    await callback.answer("Сброшено")
    await callback.message.answer(
        f"🔄 Ссылка #{url_id}: опрос сброшен. Следующий «Опрос сейчас» подтянет объявления за 24 ч.",
        reply_markup=group_url_actions(url_id, group_id),
    )


@router.callback_query(F.data.startswith("group:reset_poll:"))
async def reset_group_poll_callback(callback: CallbackQuery, db_user: User) -> None:
    group_id = int(callback.data.split(":")[-1])
    async with async_session_factory() as session:
        count = await repo.reset_group_poll_state(session, group_id, db_user.telegram_id)
        group = await repo.get_group(session, group_id, db_user.telegram_id)
    if count == 0:
        await callback.answer("Группа не найдена", show_alert=True)
        return
    await callback.answer("Сброшено")
    name = group.name if group else str(group_id)
    await callback.message.answer(
        f"🔄 Группа «{name}»: сброшен опрос по {count} ссылкам. "
        "Следующий «Опрос сейчас» подтянет объявления за 24 ч.",
        reply_markup=group_actions(group_id),
    )


@router.callback_query(F.data.startswith("group:del:"))
async def delete_group(callback: CallbackQuery, db_user: User) -> None:
    group_id = int(callback.data.split(":")[-1])
    async with async_session_factory() as session:
        ok = await repo.delete_group(session, group_id, db_user.telegram_id)
    if ok:
        await callback.message.edit_text("Группа удалена.")
    else:
        await callback.answer("Группа не найдена", show_alert=True)
    await callback.answer()


@router.callback_query(F.data.startswith("group:url:add:"))
async def add_url_start(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    group_id = int(callback.data.split(":")[-1])
    async with async_session_factory() as session:
        group = await repo.get_group(session, group_id, db_user.telegram_id)
    if group is None:
        await callback.answer("Группа не найдена", show_alert=True)
        return

    await state.set_state(AddGroupUrlStates.url)
    await state.update_data(group_id=group_id)
    await callback.message.answer(
        f"➕ <b>Добавить ссылку</b> в группу «{html.escape(group.name)}»\n\n"
        "Отправьте ссылку Kufar вида:\n"
        "<code>https://www.kufar.by/l/...</code>\n\n"
        "Отмена — /cancel",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddGroupUrlStates.url, F.text == "/cancel")
async def add_url_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добавление ссылки отменено.", reply_markup=groups_menu())


@router.message(AddGroupUrlStates.url, ~_MENU_FILTER)
async def add_url_receive(message: Message, state: FSMContext, db_user: User) -> None:
    url = (message.text or "").strip()
    if not is_kufar_url(url):
        await message.answer(
            "Нужна ссылка Kufar вида https://www.kufar.by/l/...\n"
            "Попробуйте ещё раз или /cancel"
        )
        return

    data = await state.get_data()
    group_id = data.get("group_id")
    if not group_id:
        await state.clear()
        await message.answer("Сессия устарела. Нажмите «➕ Ссылка» снова.", reply_markup=groups_menu())
        return

    async with async_session_factory() as session:
        group = await repo.get_group(session, group_id, db_user.telegram_id)
        if group is None:
            await state.clear()
            await message.answer("Группа не найдена.", reply_markup=groups_menu())
            return
        async with KufarClient() as client:
            api_query = await client.resolve_search_query(url)
            log.info(
                "group_url_added",
                user_id=db_user.telegram_id,
                group_id=group.id,
                url=url,
                api_query=api_query,
            )
            await repo.add_group_url(session, group.id, url, json.dumps(api_query, ensure_ascii=False))

    await state.clear()
    await message.answer(
        f"✅ Ссылка добавлена в «{group.name}». Всего ссылок: {len(group.urls) + 1}.",
        reply_markup=group_actions(group.id),
    )


@router.message(F.text.startswith("/addurl "))
async def add_url_command(message: Message, db_user: User) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /addurl <group_id> <url>")
        return
    try:
        group_id = int(parts[1])
    except ValueError:
        await message.answer("group_id должен быть числом")
        return
    url = parts[2].strip()
    if not is_kufar_url(url):
        await message.answer("Нужна ссылка Kufar вида https://www.kufar.by/l/...")
        return

    async with async_session_factory() as session:
        group = await repo.get_group(session, group_id, db_user.telegram_id)
        if group is None:
            await message.answer("Группа не найдена")
            return
        async with KufarClient() as client:
            api_query = await client.resolve_search_query(url)
            await repo.add_group_url(session, group.id, url, json.dumps(api_query, ensure_ascii=False))
    await message.answer(f"Ссылка добавлена в группу «{group.name}» (#{group.id}).")
