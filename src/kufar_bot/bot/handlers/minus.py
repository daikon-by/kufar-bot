from sqlalchemy import select
from sqlalchemy.orm import joinedload

import structlog
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from kufar_bot.bot.keyboards import minus_confirm_keyboard
from kufar_bot.bot.minus_draft import minus_draft_payload, selection_for_phrase
from kufar_bot.bot.minus_list_view import (
    clamp_page,
    format_minus_group_header,
    minus_phrases_page_keyboard,
    parse_minus_scope_key,
)
from kufar_bot.bot.minus_listing import (
    delete_message_safe,
    edit_listing_message_by_id,
    restore_listing_message,
)
from kufar_bot.bot.minus_nav import MINUS_MENU_BUTTONS
from kufar_bot.bot.minus_scope import (
    group_minus_phrases,
    minus_scope_from_phrase,
    minus_scope_label,
)
from kufar_bot.bot.states import AddMinusFromListingStates, AddMinusStates, EditMinusStates
from kufar_bot.db import repository as repo
from kufar_bot.db.models import NegativePhrase, User
from kufar_bot.db.session import async_session_factory

router = Router()
log = structlog.get_logger(__name__)

_NOT_MENU_BTN = ~F.text.in_(MINUS_MENU_BUTTONS)


async def _restore_listing_from_state_message(message: Message, state: FSMContext) -> bool:
    data = await state.get_data()
    listing_text = data.get("listing_text")
    message_id = data.get("listing_message_id")
    chat_id = data.get("listing_chat_id")
    ad_id = data.get("listing_ad_id")
    group_id = data.get("listing_group_id")
    if not all([listing_text, message_id, chat_id, ad_id, group_id]):
        return False
    return await restore_listing_message(
        message.bot,
        chat_id=chat_id,
        message_id=message_id,
        text=listing_text,
        ad_id=int(ad_id),
        group_id=int(group_id),
    )


@router.message(
    StateFilter(AddMinusStates, AddMinusFromListingStates, EditMinusStates),
    F.text.in_(MINUS_MENU_BUTTONS),
)
async def minus_menu_interrupt(message: Message, state: FSMContext, db_user: User) -> None:
    await state.clear()
    text = message.text or ""
    if text == "📋 Список фраз":
        await list_minus_phrases(message, db_user)
    elif text == "➕ Добавить фразу":
        await add_minus_start(message, state)
    elif text == "◀️ Назад":
        await message.answer("Главное меню", reply_markup=main_menu(db_user.is_admin))
    elif text == "⛔ Минус-слова":
        await message.answer("Минус-фразы", reply_markup=minus_menu())


@router.message(F.text == "➕ Добавить фразу")
async def add_minus_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AddMinusStates.phrase)
    await state.update_data(group_id=None)
    await message.answer(
        "Введите минус-фразу (подстрока, без учёта регистра).\nОтмена: /cancel"
    )


@router.message(AddMinusStates.phrase, _NOT_MENU_BTN)
async def add_minus_phrase(message: Message, state: FSMContext, db_user: User) -> None:
    if (message.text or "").strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=minus_menu())
        return

    phrase = (message.text or "").strip()
    if not phrase:
        await message.answer("Фраза не может быть пустой.")
        return

    await state.update_data(draft_phrase=phrase)
    await message.answer(
        f"Сохранить глобально:\n«{phrase}»",
        reply_markup=minus_confirm_keyboard(),
    )


@router.message(AddMinusFromListingStates.phrase, _NOT_MENU_BTN)
async def minus_from_listing_input(message: Message, state: FSMContext, db_user: User) -> None:
    if (message.text or "").strip() == "/cancel":
        restored = await _restore_listing_from_state_message(message, state)
        await state.clear()
        if not restored:
            await message.answer("Отменено.", reply_markup=minus_menu())
        return

    phrase = (message.text or "").strip()
    if not phrase:
        await message.answer("Фраза не может быть пустой.")
        return

    data = await state.get_data()
    group_id = data.get("group_id")
    words: list[str] = data.get("title_words") or []
    suggestions: list[str] = data.get("suggestions") or []
    subject = data.get("listing_subject") or ""
    selected = selection_for_phrase(words, phrase)

    async with async_session_factory() as session:
        scope = await minus_scope_label(
            session, db_user.telegram_id, group_id, for_action=True
        )

    manual = not selected
    await state.update_data(
        draft_phrase=phrase,
        selected_word_indices=selected,
        draft_manual=manual,
    )
    draft_text, markup = minus_draft_payload(
        scope,
        subject,
        phrase,
        words,
        selected,
        suggestions,
        manual=manual,
    )
    listing_chat_id = data.get("listing_chat_id")
    ui_message_id = data.get("minus_ui_message_id") or data.get("listing_message_id")
    if ui_message_id and listing_chat_id:
        edited = await edit_listing_message_by_id(
            message.bot,
            chat_id=int(listing_chat_id),
            message_id=int(ui_message_id),
            text=draft_text,
            reply_markup=markup,
        )
        if edited:
            await state.update_data(minus_ui_message_id=int(ui_message_id))
            await delete_message_safe(
                message.bot,
                chat_id=message.chat.id,
                message_id=message.message_id,
            )
            return
        log.warning(
            "minus_draft_edit_failed",
            user_id=db_user.telegram_id,
            chat_id=listing_chat_id,
            message_id=ui_message_id,
        )

    sent = await message.answer(
        draft_text,
        parse_mode="HTML",
        reply_markup=markup,
        reply_to_message_id=ui_message_id,
    )
    await state.update_data(minus_ui_message_id=sent.message_id)


@router.message(EditMinusStates.phrase, _NOT_MENU_BTN)
async def edit_minus_phrase(message: Message, state: FSMContext, db_user: User) -> None:
    if (message.text or "").strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=minus_menu())
        return

    phrase = (message.text or "").strip()
    if not phrase:
        await message.answer("Фраза не может быть пустой.")
        return

    data = await state.get_data()
    phrase_id = data.get("phrase_id")
    if not phrase_id:
        await state.clear()
        await message.answer("Сессия устарела.")
        return

    async with async_session_factory() as session:
        item = await repo.update_negative_phrase(session, phrase_id, db_user.telegram_id, phrase)

    await state.clear()
    if item is None:
        await message.answer("Не удалось обновить фразу.", reply_markup=minus_menu())
        return
    scope = minus_scope_from_phrase(item)
    await message.answer(
        f"✅ Обновлено ({scope}): «{item.phrase}»",
        reply_markup=minus_menu(),
    )


async def _send_minus_group_page(
    target: Message,
    phrases: list[NegativePhrase],
    *,
    group_id: int | None,
    page: int = 0,
    edit: bool = False,
) -> None:
    page = clamp_page(page, len(phrases))
    text = format_minus_group_header(phrases, page=page)
    markup = minus_phrases_page_keyboard(phrases, group_id=group_id, page=page)
    if edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)


async def _load_scope_phrases(user_id: int, group_id: int | None) -> list[NegativePhrase]:
    async with async_session_factory() as session:
        result = await session.scalars(
            select(NegativePhrase)
            .options(joinedload(NegativePhrase.group))
            .where(NegativePhrase.user_id == user_id)
            .order_by(NegativePhrase.phrase)
        )
        return [p for p in result if p.group_id == group_id]


@router.message(F.text == "📋 Список фраз")
async def list_minus_phrases(message: Message, db_user: User) -> None:
    async with async_session_factory() as session:
        result = await session.scalars(
            select(NegativePhrase)
            .options(joinedload(NegativePhrase.group))
            .where(NegativePhrase.user_id == db_user.telegram_id)
            .order_by(NegativePhrase.phrase)
        )
        phrases = list(result)
    if not phrases:
        await message.answer("Минус-фраз пока нет.", reply_markup=minus_menu())
        return
    for _, group_phrases in group_minus_phrases(phrases):
        group_id = group_phrases[0].group_id
        await _send_minus_group_page(message, group_phrases, group_id=group_id)


@router.callback_query(F.data.startswith("minus:pg:"))
async def minus_phrases_page(callback: CallbackQuery, db_user: User) -> None:
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer()
        return
    scope_key = parts[2]
    page = int(parts[3])
    group_id = parse_minus_scope_key(scope_key)
    phrases = await _load_scope_phrases(db_user.telegram_id, group_id)
    if not phrases:
        if callback.message is not None:
            await callback.message.edit_text("Минус-фраз в этом разделе нет.")
        await callback.answer()
        return
    if callback.message is not None:
        await _send_minus_group_page(
            callback.message,
            phrases,
            group_id=group_id,
            page=page,
            edit=True,
        )
    await callback.answer()


@router.callback_query(F.data == "minus:noop")
async def minus_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("minus:edit:"))
async def edit_minus_start(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    phrase_id = int(callback.data.split(":")[-1])
    async with async_session_factory() as session:
        item = await repo.get_negative_phrase(session, phrase_id, db_user.telegram_id)
    if item is None:
        await callback.answer("Фраза не найдена", show_alert=True)
        return

    await state.set_state(EditMinusStates.phrase)
    await state.update_data(phrase_id=phrase_id)
    scope = minus_scope_from_phrase(item)
    await callback.message.answer(
        f"Редактирование ({scope})\n"
        f"Текущая фраза: «{item.phrase}»\n\n"
        f"Отправьте новый текст или /cancel"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("minus:del:"))
async def delete_minus(callback: CallbackQuery, db_user: User) -> None:
    parts = callback.data.split(":")
    phrase_id = int(parts[2])
    scope_key = parts[3] if len(parts) > 3 else None
    page = int(parts[4]) if len(parts) > 4 else 0
    group_id = parse_minus_scope_key(scope_key) if scope_key else None

    async with async_session_factory() as session:
        item = await repo.get_negative_phrase(session, phrase_id, db_user.telegram_id)
        if item is None:
            await callback.answer("Не найдено", show_alert=True)
            return
        if group_id is None and scope_key is None:
            group_id = item.group_id
        ok = await repo.delete_negative_phrase(session, phrase_id, db_user.telegram_id)
        if not ok:
            await callback.answer("Не найдено", show_alert=True)
            return

    remaining = await _load_scope_phrases(db_user.telegram_id, group_id)
    if callback.message is None:
        await callback.answer("Удалено")
        return
    if remaining:
        page = clamp_page(page, len(remaining))
        await _send_minus_group_page(
            callback.message,
            remaining,
            group_id=group_id,
            page=page,
            edit=True,
        )
    else:
        await callback.message.edit_text("В этом разделе минус-фраз не осталось.")
    await callback.answer("Удалено")
