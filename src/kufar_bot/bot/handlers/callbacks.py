import html

import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from kufar_bot.bot.keyboards import minus_confirm_keyboard, minus_suggest_keyboard
from kufar_bot.bot.minus_listing import (
    edit_listing_message,
    listing_message_snapshot,
    restore_listing_message,
)
from kufar_bot.bot.states import AddMinusFromListingStates
from kufar_bot.db import repository as repo
from kufar_bot.db.models import User
from kufar_bot.db.session import async_session_factory
from kufar_bot.kufar.client import KufarClient
from kufar_bot.kufar.minus_suggest import suggest_minus_phrases

router = Router()
log = structlog.get_logger(__name__)


def _scope_label(group_id: int | None) -> str:
    return "глобально" if group_id is None else f"для группы #{group_id}"


async def _restore_listing_from_state(callback: CallbackQuery, state: FSMContext) -> bool:
    data = await state.get_data()
    listing_text = data.get("listing_text")
    message_id = data.get("listing_message_id")
    chat_id = data.get("listing_chat_id")
    ad_id = data.get("listing_ad_id")
    group_id = data.get("listing_group_id")
    if not all([listing_text, message_id, chat_id, ad_id, group_id]):
        return False
    return await restore_listing_message(
        callback.bot,
        chat_id=chat_id,
        message_id=message_id,
        text=listing_text,
        ad_id=int(ad_id),
        group_id=int(group_id),
    )


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
    await state.set_state(AddMinusFromListingStates.phrase)
    await state.update_data(
        group_id=group_id,
        ad_id=ad_id,
        listing_ad_id=ad_id,
        listing_group_id=listing_group_id,
        suggestions=suggestions,
        draft_phrase=None,
        **listing_message_snapshot(callback.message),
    )

    scope = _scope_label(group_id)
    hints = ", ".join(f"«{w}»" for w in suggestions) if suggestions else "—"
    prompt = (
        f"⛔ <b>Минус-фраза</b> ({scope})\n\n"
        f"Заголовок: {html.escape(listing.subject)}\n\n"
        f"Отправьте фразу сообщением — она ищется как подстрока.\n"
        f"Подсказки: {html.escape(hints)}\n\n"
        f"Или нажмите слово ниже, затем отредактируйте и сохраните."
    )
    edited = await edit_listing_message(
        callback.message,
        prompt,
        reply_markup=minus_suggest_keyboard(suggestions),
    )
    if not edited:
        await callback.message.answer(
            prompt,
            parse_mode="HTML",
            reply_markup=minus_suggest_keyboard(suggestions),
            reply_to_message_id=callback.message.message_id,
        )
    await callback.answer()


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


@router.callback_query(F.data.startswith("minus:hint:"))
async def minus_pick_hint(callback: CallbackQuery, state: FSMContext) -> None:
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
    await state.update_data(draft_phrase=phrase)
    group_id = data.get("group_id")
    scope = _scope_label(group_id)

    text = (
        f"Черновик ({scope}):\n<code>{html.escape(phrase)}</code>\n\n"
        "Отправьте другой текст, чтобы изменить, или нажмите «Сохранить»."
    )
    if callback.message is None:
        await callback.answer()
        return
    edited = await edit_listing_message(
        callback.message,
        text,
        reply_markup=minus_confirm_keyboard(),
    )
    if not edited:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=minus_confirm_keyboard(),
            reply_to_message_id=data.get("listing_message_id"),
        )
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
        await callback.answer(f"Сохранено: «{item.phrase}»", show_alert=True)


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
