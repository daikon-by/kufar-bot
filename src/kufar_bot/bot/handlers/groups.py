import html
import json

import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from kufar_bot.bot.group_display import (
    GroupView,
    build_group_view,
    format_group_summary,
    format_group_urls,
    group_list_keyboard,
    group_urls_keyboard,
    url_label,
)
from kufar_bot.bot.groups_nav import is_groups_menu_button
from kufar_bot.bot.keyboards import groups_menu, main_menu
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


async def _get_group_view_by_id(user_id: int, group_id: int) -> GroupView | None:
    async with async_session_factory() as session:
        group = await repo.get_group(session, group_id, user_id)
    if group is None:
        return None
    return build_group_view(group)


async def _get_group_view(db_user: User, group_id: int) -> GroupView | None:
    return await _get_group_view_by_id(db_user.telegram_id, group_id)


async def _send_group_urls(message: Message, view: GroupView) -> None:
    await message.answer(
        format_group_urls(view),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=group_urls_keyboard(view),
    )


async def _send_all_urls(message: Message, db_user: User) -> None:
    async with async_session_factory() as session:
        groups = await repo.get_user_groups(session, db_user.telegram_id)
    if not groups:
        await message.answer("Групп и ссылок пока нет.", reply_markup=groups_menu())
        return
    sent = False
    for group in groups:
        view = build_group_view(group)
        if not view.urls:
            continue
        sent = True
        await _send_group_urls(message, view)
    if not sent:
        await message.answer("Группы есть, но ссылки не добавлены.", reply_markup=groups_menu())


@nav_router.message(_MENU_FILTER, flags={"priority": 100})
async def groups_menu_nav(message: Message, state: FSMContext, db_user: User) -> None:
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


@router.message(F.text == "➕ Добавить группу")
async def add_group_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AddGroupStates.name)
    await message.answer(
        "Введите название группы (например: Дом и сад).\n\n"
        "Если группа уже есть — ссылки добавятся в неё.\n"
        "Для одного раздела удобнее: 📋 Список групп → ➕ Раздел"
    )


@router.message(AddGroupStates.name, ~_MENU_FILTER)
async def add_group_name(message: Message, state: FSMContext, db_user: User) -> None:
    name = message.text.strip()
    await state.update_data(name=name)
    async with async_session_factory() as session:
        existing = await repo.get_group_by_name(session, db_user.telegram_id, name)
    if existing:
        await state.update_data(existing_group_id=existing.id)
        await state.set_state(AddGroupStates.urls)
        await message.answer(
            f"Группа «{html.escape(name)}» уже есть ({len(existing.urls)} ссылок).\n"
            "Новые ссылки будут <b>добавлены в неё</b>.\n"
            "Формат: <code>Раздел | ссылка</code> или просто ссылка.\n"
            "/done когда готово, /cancel — отмена",
            parse_mode="HTML",
        )
        return
    await state.set_state(AddGroupStates.region_label)
    await message.answer("Регион (например: Бобруйский район). Можно «-» чтобы пропустить.")


@router.message(AddGroupStates.region_label, ~_MENU_FILTER)
async def add_group_region(message: Message, state: FSMContext) -> None:
    value = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(region_label=value)
    await state.set_state(AddGroupStates.urls)
    await message.answer(
        "Отправьте ссылки Kufar (каждая с новой строки).\n"
        "Опционально: <code>Раздел | ссылка</code>\n"
        "Когда закончите — /done\n"
        "Отмена — /cancel",
        parse_mode="HTML",
    )


def _parse_url_line(line: str) -> tuple[str, str]:
    if "|" in line:
        left, right = line.split("|", maxsplit=1)
        section = left.strip()
        url = right.strip()
        if is_kufar_url(url):
            return section, url
    return "", line.strip()


@router.message(AddGroupStates.urls, F.text == "/done")
async def add_group_done(message: Message, state: FSMContext, db_user: User) -> None:
    data = await state.get_data()
    items: list[dict[str, str]] = data.get("url_items", [])
    if not items:
        await message.answer("Нужна хотя бы одна ссылка. Отправьте URL и снова /done")
        return

    async with async_session_factory() as session:
        existing_id = data.get("existing_group_id")
        if existing_id:
            group = await repo.get_group(session, existing_id, db_user.telegram_id)
            created = False
        else:
            group = await repo.create_group(
                session,
                db_user.telegram_id,
                data["name"],
                data.get("region_label", ""),
            )
            created = True
        if group is None:
            await message.answer("Группа не найдена.", reply_markup=groups_menu())
            await state.clear()
            return

        group = await repo.get_group(session, group.id, db_user.telegram_id)
        if group is None:
            await message.answer("Группа не найдена.", reply_markup=groups_menu())
            await state.clear()
            return

        existing_urls = {item.url for item in group.urls}
        added = 0
        skipped = 0
        async with KufarClient() as client:
            for item in items:
                if item["url"] in existing_urls:
                    skipped += 1
                    continue
                api_query = await client.resolve_search_query(item["url"])
                log.info(
                    "group_url_added",
                    user_id=db_user.telegram_id,
                    group_id=group.id,
                    url=item["url"],
                    section=item.get("section", ""),
                    api_query=api_query,
                )
                await repo.add_group_url(
                    session,
                    group.id,
                    item["url"],
                    json.dumps(api_query, ensure_ascii=False),
                    section_label=item.get("section", ""),
                )
                added += 1

    await state.clear()
    if created:
        text = f"Группа «{group.name}» создана. Ссылок: {added}."
    elif added:
        text = f"В группу «{group.name}» добавлено ссылок: {added}."
        if skipped:
            text += f" Пропущено дубликатов: {skipped}."
    else:
        text = f"Все ссылки уже есть в группе «{group.name}»."
    await message.answer(text, reply_markup=groups_menu())


@router.message(AddGroupStates.urls, ~_MENU_FILTER, F.text != "/done", F.text != "/cancel")
async def add_group_urls(message: Message, state: FSMContext) -> None:
    lines = [line.strip() for line in (message.text or "").splitlines() if line.strip()]
    valid: list[dict[str, str]] = []
    for line in lines:
        section, url = _parse_url_line(line)
        if not is_kufar_url(url):
            await message.answer(f"Пропущена невалидная ссылка:\n{line}")
            continue
        valid.append({"section": section, "url": url})
    if not valid:
        await message.answer("Не найдено валидных ссылок Kufar (/l/...).")
        return
    data = await state.get_data()
    items = data.get("url_items", [])
    items.extend(valid)
    await state.update_data(url_items=items)
    await message.answer(f"Добавлено ссылок: {len(valid)}. Всего: {len(items)}. Ещё ссылки или /done")


@router.message(AddGroupStates.urls, F.text == "/cancel")
async def add_group_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добавление группы отменено.", reply_markup=groups_menu())


@router.message(F.text == "📋 Список групп")
async def list_groups(message: Message, state: FSMContext, db_user: User) -> None:
    await state.clear()
    async with async_session_factory() as session:
        groups = await repo.get_user_groups(session, db_user.telegram_id)
    if not groups:
        await message.answer("Групп пока нет.", reply_markup=groups_menu())
        return
    for group in groups:
        view = build_group_view(group)
        await message.answer(
            format_group_summary(view),
            parse_mode="HTML",
            reply_markup=group_list_keyboard(view),
        )


@router.message(F.text == "🔗 Мои ссылки")
async def list_all_urls(message: Message, state: FSMContext, db_user: User) -> None:
    await state.clear()
    log.info("list_all_urls", user_id=db_user.telegram_id)
    await _send_all_urls(message, db_user)


@router.callback_query(F.data.startswith("group:urls:"))
async def list_group_urls_callback(callback: CallbackQuery, db_user: User) -> None:
    group_id = int(callback.data.split(":")[-1])
    view = await _get_group_view(db_user, group_id)
    if view is None:
        await callback.answer("Группа не найдена", show_alert=True)
        return
    log.info("list_group_urls", user_id=db_user.telegram_id, group_id=group_id, urls=len(view.urls))
    await callback.message.answer(
        format_group_urls(view),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=group_urls_keyboard(view),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("group:url:del:"))
async def delete_group_url_callback(callback: CallbackQuery, db_user: User) -> None:
    parts = callback.data.split(":")
    url_id = int(parts[3])
    group_id = int(parts[4])
    async with async_session_factory() as session:
        ok = await repo.delete_group_url(session, url_id, db_user.telegram_id)
    if not ok:
        await callback.answer("Ссылка не найдена", show_alert=True)
        return
    view = await _get_group_view(db_user, group_id)
    label = url_label(view, url_id) if view else "ссылка"
    await callback.message.edit_text(f"🗑 {label.capitalize()} удалена")
    await callback.answer("Удалено")
    if view and view.urls:
        await _send_group_urls(callback.message, view)
    elif view:
        await callback.message.answer(
            f"В группе «{view.name}» ссылок не осталось.",
            reply_markup=group_list_keyboard(view),
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
    view = await _get_group_view(db_user, group_id)
    label = url_label(view, url_id) if view else "ссылка"
    name = view.name if view else "группе"
    await callback.message.answer(
        f"🔄 {label.capitalize()} в «{name}»: опрос сброшен. "
        "Следующий «Опрос сейчас» подтянет объявления за 24 ч.",
        reply_markup=group_urls_keyboard(view) if view and view.urls else group_list_keyboard(view) if view else None,
    )


@router.callback_query(F.data.startswith("group:sec:reset:"))
async def reset_section_poll_callback(callback: CallbackQuery, db_user: User) -> None:
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer("Ошибка", show_alert=True)
        return
    group_id = int(parts[3])
    section_idx = int(parts[4])
    view = await _get_group_view(db_user, group_id)
    if view is None or section_idx < 0 or section_idx >= len(view.sections):
        await callback.answer("Раздел не найден", show_alert=True)
        return
    section = view.sections[section_idx]
    async with async_session_factory() as session:
        count = await repo.reset_section_poll_state(session, group_id, db_user.telegram_id, section)
    if count == 0:
        await callback.answer("Раздел не найден", show_alert=True)
        return
    await callback.answer("Сброшено")
    name = view.name
    await callback.message.answer(
        f"🔄 Раздел «{section}» в «{name}»: сброшен опрос по {count} ссылкам.",
        reply_markup=group_urls_keyboard(view) if view and view.urls else None,
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
    view = build_group_view(group) if group else None
    await callback.message.answer(
        f"🔄 Группа «{name}»: сброшен опрос по {count} ссылкам. "
        "Следующий «Опрос сейчас» подтянет объявления за 24 ч.",
        reply_markup=group_list_keyboard(view) if view else None,
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


async def _start_add_url(callback: CallbackQuery, state: FSMContext, group_id: int, *, require_section: bool) -> None:
    async with async_session_factory() as session:
        group = await repo.get_group(session, group_id, callback.from_user.id)
    if group is None:
        await callback.answer("Группа не найдена", show_alert=True)
        return
    await state.set_state(AddGroupUrlStates.section_label)
    await state.update_data(group_id=group_id, require_section=require_section)
    if require_section:
        prompt = (
            f"➕ <b>Новый раздел</b> в «{html.escape(group.name)}»\n\n"
            "Введите название раздела (например: Сад и огород),\n"
            "затем отправьте ссылку Kufar.\n\n"
            "Отмена — /cancel"
        )
    else:
        prompt = (
            f"➕ <b>Добавить ссылку</b> в «{html.escape(group.name)}»\n\n"
            "Раздел (можно «-» без раздела), затем ссылка.\n"
            "Или сразу отправьте ссылку.\n\n"
            "Отмена — /cancel"
        )
    await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("group:section:add:"))
async def add_section_start(callback: CallbackQuery, state: FSMContext) -> None:
    group_id = int(callback.data.split(":")[-1])
    await _start_add_url(callback, state, group_id, require_section=True)


@router.callback_query(F.data.startswith("group:url:add:"))
async def add_url_start(callback: CallbackQuery, state: FSMContext) -> None:
    group_id = int(callback.data.split(":")[-1])
    await _start_add_url(callback, state, group_id, require_section=False)


@router.message(AddGroupUrlStates.section_label, F.text == "/cancel")
@router.message(AddGroupUrlStates.url, F.text == "/cancel")
async def add_url_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добавление отменено.", reply_markup=groups_menu())


@router.message(AddGroupUrlStates.section_label, ~_MENU_FILTER)
async def add_url_section(message: Message, state: FSMContext, db_user: User) -> None:
    raw = (message.text or "").strip()
    data = await state.get_data()
    require_section = data.get("require_section", False)

    if "|" in raw:
        section, url = _parse_url_line(raw)
        if is_kufar_url(url):
            await state.update_data(section_label=section, pending_url=url)
            await state.set_state(AddGroupUrlStates.url)
            await _save_pending_url(message, state, db_user.telegram_id)
            return

    if is_kufar_url(raw) and not require_section:
        await state.update_data(section_label="", pending_url=raw)
        await state.set_state(AddGroupUrlStates.url)
        await _save_pending_url(message, state, db_user.telegram_id)
        return

    if raw == "-" and not require_section:
        section = ""
    elif not raw and require_section:
        await message.answer("Укажите название раздела.")
        return
    else:
        section = raw

    await state.update_data(section_label=section)
    await state.set_state(AddGroupUrlStates.url)
    hint = "Теперь отправьте ссылку Kufar." if section else "Теперь отправьте ссылку Kufar (раздел не задан)."
    await message.answer(hint)


@router.message(AddGroupUrlStates.url, ~_MENU_FILTER)
async def add_url_receive(message: Message, state: FSMContext, db_user: User) -> None:
    url = (message.text or "").strip()
    if not is_kufar_url(url):
        await message.answer("Нужна ссылка Kufar вида https://www.kufar.by/l/...\nПопробуйте ещё раз или /cancel")
        return
    await state.update_data(pending_url=url)
    await _save_pending_url(message, state, db_user.telegram_id)


async def _save_pending_url(message: Message, state: FSMContext, user_id: int) -> None:
    data = await state.get_data()
    group_id = data.get("group_id")
    url = data.get("pending_url")
    section = (data.get("section_label") or "").strip()
    require_section = data.get("require_section", False)
    if not group_id or not url:
        await state.clear()
        await message.answer("Сессия устарела.", reply_markup=groups_menu())
        return
    if require_section and not section:
        await message.answer("Сначала укажите название раздела.")
        return

    async with async_session_factory() as session:
        group = await repo.get_group(session, group_id, user_id)
        if group is None:
            await state.clear()
            await message.answer("Группа не найдена.", reply_markup=groups_menu())
            return
        if any(item.url == url for item in group.urls):
            await state.clear()
            await message.answer(
                f"Эта ссылка уже есть в «{group.name}».",
                reply_markup=group_list_keyboard(build_group_view(group)),
            )
            return
        async with KufarClient() as client:
            api_query = await client.resolve_search_query(url)
            await repo.add_group_url(
                session,
                group.id,
                url,
                json.dumps(api_query, ensure_ascii=False),
                section_label=section,
            )

    await state.clear()
    view = await _get_group_view_by_id(user_id, group_id)
    total = len(view.urls) if view else 1
    extra = f" (раздел «{section}»)" if section else ""
    await message.answer(
        f"✅ Ссылка добавлена в «{group.name}»{extra}. Всего ссылок: {total}.",
        reply_markup=group_list_keyboard(view) if view else None,
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
    await message.answer(f"Ссылка добавлена в группу «{group.name}».")
