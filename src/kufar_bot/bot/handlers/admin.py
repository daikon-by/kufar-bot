import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from kufar_bot.bot.users_list_view import format_users_page, users_page_keyboard
from kufar_bot.db import repository as repo
from kufar_bot.db.models import User
from kufar_bot.db.session import async_session_factory

router = Router()
log = structlog.get_logger(__name__)


def _parse_target_and_days(text: str) -> tuple[int | None, int | None]:
    parts = text.split()
    if len(parts) < 2:
        return None, None
    try:
        target_id = int(parts[1])
    except ValueError:
        return None, None
    days = None
    if len(parts) >= 3:
        try:
            days = int(parts[2])
        except ValueError:
            days = None
    return target_id, days


async def _load_users() -> list[User]:
    async with async_session_factory() as session:
        return await repo.list_users(session)


async def _send_users_page(target: Message, *, page: int = 0, edit: bool = False) -> None:
    users = await _load_users()
    text = format_users_page(users, page=page)
    markup = users_page_keyboard(users, page=page)
    if edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)


async def _grant_access(bot, target_id: int) -> User:
    async with async_session_factory() as session:
        user = await repo.authorize_user(session, target_id)
    try:
        await bot.send_message(
            target_id,
            "✅ Вам выдан доступ к боту. Нажмите /start",
        )
    except Exception as exc:
        log.warning("access_notify_user_failed", user_id=target_id, error=str(exc))
    return user


async def _revoke_access(target_id: int) -> bool:
    async with async_session_factory() as session:
        return await repo.revoke_user(session, target_id)


@router.message(Command("allow"))
async def cmd_allow(message: Message, db_user: User) -> None:
    if not db_user.is_admin:
        await message.answer("Команда только для администратора.")
        return
    target_id, days = _parse_target_and_days(message.text or "")
    if target_id is None:
        await message.answer("Использование: /allow <telegram_id> [дней]")
        return
    async with async_session_factory() as session:
        user = await repo.authorize_user(session, target_id, days=days)
    suffix = f" на {days} дн." if days else " без срока"
    await message.answer(f"Доступ выдан пользователю {user.telegram_id}{suffix}.")


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, db_user: User) -> None:
    if not db_user.is_admin:
        await message.answer("Команда только для администратора.")
        return
    target_id, _ = _parse_target_and_days(message.text or "")
    if target_id is None:
        await message.answer("Использование: /revoke <telegram_id>")
        return
    ok = await _revoke_access(target_id)
    if ok:
        await message.answer(f"Доступ отозван у {target_id}.")
    else:
        await message.answer("Не удалось отозвать доступ (пользователь не найден или это админ).")


@router.message(Command("users"))
async def cmd_users(message: Message, db_user: User) -> None:
    if not db_user.is_admin:
        await message.answer("Команда только для администратора.")
        return
    await _send_users_page(message)


@router.message(lambda m: m.text == "👥 Пользователи")
async def users_button(message: Message, db_user: User) -> None:
    if not db_user.is_admin:
        return
    await _send_users_page(message)


@router.callback_query(F.data.startswith("admin:users:pg:"))
async def users_page(callback: CallbackQuery, db_user: User) -> None:
    if not db_user.is_admin:
        await callback.answer("Только для администратора", show_alert=True)
        return
    page = int(callback.data.split(":")[-1])
    if callback.message is not None:
        await _send_users_page(callback.message, page=page, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:allow:"))
async def users_allow(callback: CallbackQuery, db_user: User) -> None:
    if not db_user.is_admin:
        await callback.answer("Только для администратора", show_alert=True)
        return
    parts = callback.data.split(":")
    target_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    await _grant_access(callback.bot, target_id)
    if callback.message is not None and callback.message.text and callback.message.text.startswith("🆕"):
        await callback.message.edit_text(
            f"✅ Доступ выдан пользователю <code>{target_id}</code>",
            parse_mode="HTML",
        )
    elif callback.message is not None:
        await _send_users_page(callback.message, page=page, edit=True)
    await callback.answer("Доступ выдан")


@router.callback_query(F.data.startswith("admin:revoke:"))
async def users_revoke(callback: CallbackQuery, db_user: User) -> None:
    if not db_user.is_admin:
        await callback.answer("Только для администратора", show_alert=True)
        return
    parts = callback.data.split(":")
    target_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    ok = await _revoke_access(target_id)
    if not ok:
        await callback.answer("Не удалось отозвать (админ или не найден)", show_alert=True)
        return
    if callback.message is not None:
        await _send_users_page(callback.message, page=page, edit=True)
    await callback.answer("Доступ отозван")


@router.callback_query(F.data.startswith("admin:dismiss:"))
async def dismiss_new_user(callback: CallbackQuery, db_user: User) -> None:
    if not db_user.is_admin:
        await callback.answer("Только для администратора", show_alert=True)
        return
    target_id = int(callback.data.split(":")[-1])
    if callback.message is not None:
        await callback.message.edit_text(
            f"Заявка от <code>{target_id}</code> оставлена без доступа.",
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data == "admin:noop")
async def admin_noop(callback: CallbackQuery) -> None:
    await callback.answer()
