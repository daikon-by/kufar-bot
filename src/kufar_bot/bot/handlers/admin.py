from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from kufar_bot.db import repository as repo
from kufar_bot.db.models import User
from kufar_bot.db.session import async_session_factory

router = Router()


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
    async with async_session_factory() as session:
        ok = await repo.revoke_user(session, target_id)
    if ok:
        await message.answer(f"Доступ отозван у {target_id}.")
    else:
        await message.answer("Не удалось отозвать доступ (пользователь не найден или это админ).")


@router.message(Command("users"))
async def cmd_users(message: Message, db_user: User) -> None:
    if not db_user.is_admin:
        await message.answer("Команда только для администратора.")
        return
    await _send_users_list(message)


async def _send_users_list(message: Message) -> None:
    async with async_session_factory() as session:
        users = await repo.list_users(session)
    if not users:
        await message.answer("Пользователей нет.")
        return
    lines = ["<b>Пользователи:</b>"]
    for user in users:
        status = "✅" if repo.user_has_access(user) else "❌"
        admin = " 👑" if user.is_admin else ""
        exp = ""
        if user.expires_at:
            exp = f" до {user.expires_at.astimezone().strftime('%d.%m.%Y')}"
        uname = f" @{user.username}" if user.username else ""
        lines.append(f"{status}{admin} <code>{user.telegram_id}</code>{uname}{exp}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(lambda m: m.text == "👥 Пользователи")
async def users_button(message: Message, db_user: User) -> None:
    if not db_user.is_admin:
        return
    await _send_users_list(message)
