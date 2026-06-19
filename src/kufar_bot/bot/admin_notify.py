from __future__ import annotations

import html

import structlog
from aiogram import Bot

from kufar_bot.bot.users_list_view import new_user_notification_keyboard
from kufar_bot.config import settings

log = structlog.get_logger(__name__)


def format_new_user_notification(*, telegram_id: int, username: str | None) -> str:
    uname = f"@{html.escape(username)}" if username else "без username"
    return (
        "🆕 <b>Новый пользователь</b>\n\n"
        f"ID: <code>{telegram_id}</code>\n"
        f"Username: {uname}"
    )


async def notify_admins_new_user(
    bot: Bot,
    *,
    telegram_id: int,
    username: str | None,
) -> None:
    if telegram_id in settings.admin_id_list:
        return

    text = format_new_user_notification(telegram_id=telegram_id, username=username)
    markup = new_user_notification_keyboard(telegram_id)
    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(
                admin_id,
                text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        except Exception as exc:
            log.warning(
                "admin_notify_new_user_failed",
                admin_id=admin_id,
                user_id=telegram_id,
                error=str(exc),
            )
