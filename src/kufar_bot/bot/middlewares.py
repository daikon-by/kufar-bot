from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from kufar_bot.bot.admin_notify import notify_admins_new_user
from kufar_bot.config import settings
from kufar_bot.db import repository as repo
from kufar_bot.db.session import async_session_factory


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        bot = data.get("bot")
        async with async_session_factory() as session:
            db_user, created = await repo.get_or_create_user(session, user.id, user.username)
            await session.commit()
            data["db_user"] = db_user

        if created and bot is not None:
            await notify_admins_new_user(
                bot,
                telegram_id=user.id,
                username=user.username,
            )

        if not repo.user_has_access(db_user):
            if isinstance(event, Message) and event.text and event.text.startswith("/start"):
                return await handler(event, data)
            denied = (
                f"Доступ закрыт. Напишите администратору @{settings.admin_username} "
                f"и сообщите ваш ID: <code>{user.id}</code>"
            )
            if isinstance(event, Message):
                await event.answer(denied, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer("Нет доступа", show_alert=True)
            return None
        return await handler(event, data)
