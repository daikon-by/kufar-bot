import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from kufar_bot.bot.minus_draft import (
    draft_from_selection,
    initial_draft_state,
    minus_draft_payload,
    selection_for_phrase,
)
from kufar_bot.bot.minus_listing import (
    delete_message_safe,
    edit_listing_message,
    edit_listing_message_by_id,
    listing_message_snapshot,
    restore_listing_message,
)
from kufar_bot.bot.minus_scope import minus_scope_label
from kufar_bot.bot.states import AddMinusFromListingStates
from kufar_bot.db import repository as repo
from kufar_bot.db.models import User
from kufar_bot.db.session import async_session_factory
from kufar_bot.kufar.client import KufarClient
from kufar_bot.kufar.minus_suggest import suggest_minus_phrases

router = Router()
log = structlog.get_logger(__name__)


async def _restore_listing_from_state(callback: CallbackQuery, state: FSMContext) -> bool:
    data = await state.get_data()
    listing_text = data.get("listing_text")
    message_id = data.get("listing_message_id")
    chat_id = data.get("listing_chat_id")
    ad_id = data.get("listing_ad_id")
    group_id = data.get("listing_group_id")
    if not all([listing_text, message_id, chat_id, ad_id, group_id]):
        return False
    restored = await restore_listing_message(
        callback.bot,
        chat_id=chat_id,
        message_id=message_id,
        text=listing_text,
        ad_id=int(ad_id),
        group_id=int(group_id),
    )
    if restored:
        await _cleanup_minus_ui_messages(callback, data, keep_message_id=message_id)
    return restored


async def _cleanup_minus_ui_messages(
    callback: CallbackQuery,
    data: dict,
    *,
    keep_message_id: int,
) -> None:
    chat_id = data.get("listing_chat_id")
    if chat_id is None:
        return
    ui_message_id = data.get("minus_ui_message_id")
    if ui_message_id and ui_message_id != keep_message_id:
        await delete_message_safe(callback.bot, chat_id=chat_id, message_id=ui_message_id)
    if (
        callback.message is not None
        and callback.message.message_id != keep_message_id
        and callback.message.message_id != ui_message_id
    ):
        await delete_message_safe(
            callback.bot,
            chat_id=chat_id,
            message_id=callback.message.message_id,
        )


async def _refresh_minus_draft_message(
    callback: CallbackQuery,
    state: FSMContext,
    db_user: User,
    *,
    manual: bool = False,
) -> int | None:
    if callback.message is None:
        return None
    data = await state.get_data()
    words: list[str] = data.get("title_words") or []
    selected: list[int] = data.get("selected_word_indices") or []
    draft = (data.get("draft_phrase") or "").strip()
    subject = data.get("listing_subject") or ""
    suggestions: list[str] = data.get("suggestions") or []
    group_id = data.get("group_id")

    async with async_session_factory() as session:
        scope = await minus_scope_label(
            session, db_user.telegram_id, group_id, for_action=True
        )

    text, markup = minus_draft_payload(
        scope,
        subject,
        draft,
        words,
        selected,
        suggestions,
        manual=manual,
    )
    ui_message_id = data.get("minus_ui_message_id") or callback.message.message_id
    edited = await edit_listing_message_by_id(
        callback.bot,
        chat_id=int(data.get("listing_chat_id") or callback.message.chat.id),
        message_id=int(ui_message_id),
        text=text,
        reply_markup=markup,
    )
    if edited:
        await state.update_data(minus_ui_message_id=int(ui_message_id))
        return int(ui_message_id)

    sent = await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=markup,
        reply_to_message_id=data.get("listing_message_id"),
    )
    await state.update_data(minus_ui_message_id=sent.message_id)
    return sent.message_id


async def _start_minus_from_listing(
    callback: CallbackQuery,
    state: FSMContext,
    db_user: User,
    ad_id: int,
    *,
    group_id: int | None,
    listing_group_id: int,
) -> None:
    if callback.message is None:
        await callback.answer("Сообщение недоступно", show_alert=True)
        return

    async with KufarClient() as client:
        listing = await client.fetch_listing(ad_id)
    if listing is None:
        await callback.answer("Объявление недоступно", show_alert=True)
        return

    suggestions = suggest_minus_phrases(listing.subject)
    words, selected, draft = initial_draft_state(listing.subject)
    await state.set_state(AddMinusFromListingStates.phrase)
    await state.update_data(
        group_id=group_id,
        ad_id=ad_id,
        listing_ad_id=ad_id,
        listing_group_id=listing_group_id,
        listing_subject=listing.subject,
        title_words=words,
        selected_word_indices=selected,
        suggestions=suggestions,
        draft_phrase=draft,
        draft_manual=False,
        **listing_message_snapshot(callback.message),
    )

    async with async_session_factory() as session:
        scope = await minus_scope_label(
            session, db_user.telegram_id, group_id, for_action=True
        )
    text, markup = minus_draft_payload(
        scope,
        listing.subject,
        draft,
        words,
        selected,
        suggestions,
    )
    ui_message_id = callback.message.message_id
    edited = await edit_listing_message(
        callback.message,
        text,
        reply_markup=markup,
    )
    if not edited:
        sent = await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=markup,
            reply_to_message_id=callback.message.message_id,
        )
        ui_message_id = sent.message_id
    await state.update_data(minus_ui_message_id=ui_message_id)
    await callback.answer()


@router.callback_query(F.data.startswith("fav:add:"))
async def add_favorite(callback: CallbackQuery, db_user: User) -> None:
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Ошибка", show_alert=True)
        return
    ad_id = int(parts[2])

    async with KufarClient() as client:
        listing = await client.fetch_listing(ad_id)
    if listing is None:
        await callback.answer("Объявление недоступно", show_alert=True)
        return

    if listing.price_byn is not None:
        price = listing.price_byn
        currency = "BYN"
    elif listing.price_usd is not None:
        price = listing.price_usd
        currency = "USD"
    else:
        price = None
        currency = listing.currency or "BYN"

    async with async_session_factory() as session:
        fav = await repo.add_favorite(
            session,
            db_user.telegram_id,
            ad_id,
            listing.subject,
            listing.url,
            listing.display_photo_url,
            price,
            currency,
        )

    await callback.answer(f"⭐ В избранном: {fav.title[:40]}", show_alert=False)


@router.callback_query(F.data.startswith("minus:global:"))
async def minus_from_listing_global(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    parts = callback.data.split(":")
    ad_id = int(parts[2])
    listing_group_id = int(parts[3])
    await _start_minus_from_listing(
        callback, state, db_user, ad_id, group_id=None, listing_group_id=listing_group_id
    )


@router.callback_query(F.data.startswith("minus:group:"))
async def minus_from_listing_group(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    parts = callback.data.split(":")
    ad_id = int(parts[2])
    listing_group_id = int(parts[3])
    await _start_minus_from_listing(
        callback, state, db_user, ad_id, group_id=listing_group_id, listing_group_id=listing_group_id
    )


@router.callback_query(F.data.startswith("minus:wd:"))
async def minus_toggle_word(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    data = await state.get_data()
    words: list[str] = data.get("title_words") or []
    if not words:
        await callback.answer("Сессия устарела", show_alert=True)
        return

    token = callback.data.split(":")[-1]
    if token == "all":
        selected = list(range(len(words)))
    else:
        idx = int(token)
        if idx < 0 or idx >= len(words):
            await callback.answer("Неверное слово", show_alert=True)
            return
        selected = list(data.get("selected_word_indices") or [])
        if idx in selected:
            selected = [i for i in selected if i != idx]
        else:
            selected.append(idx)

    draft = draft_from_selection(words, selected)
    await state.update_data(
        selected_word_indices=selected,
        draft_phrase=draft,
        draft_manual=False,
    )
    await _refresh_minus_draft_message(callback, state, db_user)
    await callback.answer()


@router.callback_query(F.data.startswith("minus:hint:"))
async def minus_pick_hint(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    data = await state.get_data()
    if not data.get("suggestions"):
        await callback.answer("Сессия устарела, нажмите «В минус» снова", show_alert=True)
        return

    idx = int(callback.data.split(":")[-1])
    suggestions: list[str] = data["suggestions"]
    if idx < 0 or idx >= len(suggestions):
        await callback.answer("Неверная подсказка", show_alert=True)
        return

    phrase = suggestions[idx]
    words: list[str] = data.get("title_words") or []
    selected = selection_for_phrase(words, phrase)
    await state.update_data(
        draft_phrase=phrase,
        selected_word_indices=selected,
        draft_manual=not selected,
    )
    await _refresh_minus_draft_message(callback, state, db_user, manual=not selected)
    await callback.answer()


@router.callback_query(F.data == "minus:save")
async def minus_save_draft(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    data = await state.get_data()
    phrase = (data.get("draft_phrase") or "").strip()
    if not phrase:
        await callback.answer("Сначала введите или выберите фразу", show_alert=True)
        return

    group_id = data.get("group_id")
    async with async_session_factory() as session:
        item = await repo.add_negative_phrase(
            session,
            db_user.telegram_id,
            phrase,
            group_id=group_id if group_id else None,
        )

    restored = await _restore_listing_from_state(callback, state)
    await state.clear()
    if item is None:
        if not restored and callback.message is not None:
            await callback.message.edit_text("Не удалось сохранить фразу.")
        await callback.answer("Не удалось сохранить", show_alert=True)
    else:
        await callback.answer()


@router.callback_query(F.data == "minus:cancel")
async def minus_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    restored = await _restore_listing_from_state(callback, state)
    await state.clear()
    if restored:
        await callback.answer("Отменено")
    elif callback.message is not None:
        await callback.message.edit_text("Добавление минус-фразы отменено.")
        await callback.answer()
    else:
        await callback.answer("Отменено")


@router.callback_query(F.data == "minus:back_listing")
async def minus_back_listing(callback: CallbackQuery, state: FSMContext) -> None:
    restored = await _restore_listing_from_state(callback, state)
    await state.clear()
    if restored:
        await callback.answer("Вернулись к объявлению")
    else:
        await callback.answer("Не удалось восстановить объявление", show_alert=True)
