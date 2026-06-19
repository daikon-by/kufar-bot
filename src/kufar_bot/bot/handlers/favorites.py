from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from kufar_bot.bot.favorites_list_view import (
    clamp_page,
    favorites_page_keyboard,
    format_favorites_page,
)
from kufar_bot.db import repository as repo
from kufar_bot.db.models import User
from kufar_bot.db.session import async_session_factory

router = Router()


async def _load_favorites(user_id: int):
    async with async_session_factory() as session:
        return await repo.get_favorites(session, user_id, active_only=True)


async def _send_favorites_page(
    target: Message,
    favorites,
    *,
    page: int = 0,
    edit: bool = False,
) -> None:
    page = clamp_page(page, len(favorites))
    text = format_favorites_page(favorites, page=page)
    markup = favorites_page_keyboard(favorites, page=page) if favorites else None
    if edit:
        await target.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
    else:
        await target.answer(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )


@router.message(F.text == "⭐ Избранное")
async def list_favorites(message: Message, db_user: User) -> None:
    favorites = await _load_favorites(db_user.telegram_id)
    if not favorites:
        await message.answer("Избранное пусто. Нажмите «В избранное» под объявлением.")
        return
    await _send_favorites_page(message, favorites)


@router.callback_query(F.data.startswith("fav:pg:"))
async def favorites_page(callback: CallbackQuery, db_user: User) -> None:
    page = int(callback.data.split(":")[-1])
    favorites = await _load_favorites(db_user.telegram_id)
    if callback.message is None:
        await callback.answer()
        return
    if not favorites:
        await callback.message.edit_text("Избранное пусто.")
        await callback.answer()
        return
    page = clamp_page(page, len(favorites))
    await _send_favorites_page(callback.message, favorites, page=page, edit=True)
    await callback.answer()


@router.callback_query(F.data == "fav:noop")
async def favorites_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("fav:del:"))
async def delete_favorite(callback: CallbackQuery, db_user: User) -> None:
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Ошибка", show_alert=True)
        return
    favorite_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0

    async with async_session_factory() as session:
        ok = await repo.remove_favorite(session, favorite_id, db_user.telegram_id)

    if not ok:
        await callback.answer("Не найдено", show_alert=True)
        return

    favorites = await _load_favorites(db_user.telegram_id)
    if callback.message is None:
        await callback.answer("Удалено")
        return
    if favorites:
        page = clamp_page(page, len(favorites))
        await _send_favorites_page(callback.message, favorites, page=page, edit=True)
    else:
        await callback.message.edit_text("Избранное пусто.")
    await callback.answer("Удалено")
