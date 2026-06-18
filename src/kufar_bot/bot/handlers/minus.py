import html

from sqlalchemy import select

import structlog
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from kufar_bot.bot.keyboards import main_menu, minus_confirm_keyboard, minus_menu, minus_phrase_actions
from kufar_bot.bot.minus_listing import restore_listing_message
from kufar_bot.bot.minus_nav import MINUS_MENU_BUTTONS
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
    scope = "глобально" if group_id is None else f"для группы #{group_id}"

    await state.update_data(draft_phrase=phrase)
    draft_text = (
        f"Сохранить {scope}:\n<code>{html.escape(phrase)}</code>\n\n"
        "Нажмите «Сохранить» или «К объявлению»."
    )
    listing_message_id = data.get("listing_message_id")
    listing_chat_id = data.get("listing_chat_id")
    if listing_message_id and listing_chat_id:
        try:
            from aiogram.types import Message as TgMessage

            stub = TgMessage.model_construct(
                message_id=listing_message_id,
                chat=message.chat.model_copy(update={"id": listing_chat_id}),
            )
            # edit via bot directly
            await message.bot.edit_message_text(
                chat_id=listing_chat_id,
                message_id=listing_message_id,
                text=draft_text,
                reply_markup=minus_confirm_keyboard(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return
        except Exception:
            log.exception("minus_draft_edit_failed", user_id=db_user.telegram_id)

    await message.answer(
        draft_text,
        parse_mode="HTML",
        reply_markup=minus_confirm_keyboard(),
        reply_to_message_id=listing_message_id,
    )


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
    scope = "глобально" if item.group_id is None else f"группа #{item.group_id}"
    await message.answer(
        f"✅ Обновлено ({scope}): «{item.phrase}»",
        reply_markup=minus_menu(),
    )


@router.message(F.text == "📋 Список фраз")
async def list_minus_phrases(message: Message, db_user: User) -> None:
    async with async_session_factory() as session:
        result = await session.scalars(
            select(NegativePhrase)
            .where(NegativePhrase.user_id == db_user.telegram_id)
            .order_by(NegativePhrase.phrase)
        )
        phrases = list(result)
    if not phrases:
        await message.answer("Минус-фраз пока нет.", reply_markup=minus_menu())
        return
    for item in phrases:
        scope = "глобально" if item.group_id is None else f"группа #{item.group_id}"
        await message.answer(
            f"«{item.phrase}» ({scope})",
            reply_markup=minus_phrase_actions(item.id),
        )


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
    scope = "глобально" if item.group_id is None else f"группа #{item.group_id}"
    await callback.message.answer(
        f"Редактирование ({scope})\n"
        f"Текущая фраза: «{item.phrase}»\n\n"
        f"Отправьте новый текст или /cancel"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("minus:del:"))
async def delete_minus(callback: CallbackQuery, db_user: User) -> None:
    phrase_id = int(callback.data.split(":")[-1])
    async with async_session_factory() as session:
        ok = await repo.delete_negative_phrase(session, phrase_id, db_user.telegram_id)
    if ok:
        await callback.message.edit_text("Фраза удалена.")
    else:
        await callback.answer("Не найдено", show_alert=True)
    await callback.answer()
