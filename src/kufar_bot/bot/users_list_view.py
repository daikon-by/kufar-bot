from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kufar_bot.db import repository as repo
from kufar_bot.db.models import User

PAGE_SIZE = 8


def clamp_page(page: int, total: int, page_size: int = PAGE_SIZE) -> int:
    if total <= 0:
        return 0
    pages = (total + page_size - 1) // page_size
    return max(0, min(page, pages - 1))


def _user_line(user: User, idx: int) -> str:
    status = "✅" if repo.user_has_access(user) else "❌"
    admin = " 👑" if user.is_admin else ""
    uname = f" @{html.escape(user.username)}" if user.username else ""
    exp = ""
    if user.expires_at:
        exp = f" · до {user.expires_at.astimezone().strftime('%d.%m.%Y')}"
    return f"{idx}. {status}{admin} <code>{user.telegram_id}</code>{uname}{exp}"


def format_users_page(users: list[User], *, page: int, page_size: int = PAGE_SIZE) -> str:
    total = len(users)
    if total == 0:
        return "<b>Пользователи</b>\n<i>пока никого нет</i>"

    page = clamp_page(page, total, page_size)
    chunk = users[page * page_size : (page + 1) * page_size]
    lines = ["<b>Пользователи</b>"]
    if total > page_size:
        start = page * page_size + 1
        end = min((page + 1) * page_size, total)
        lines.append(f"<i>{start}–{end} из {total}</i>")
    else:
        lines.append(f"<i>{total} — выдайте или отзовите доступ кнопками ниже</i>")

    for idx, user in enumerate(chunk, start=page * page_size + 1):
        lines.append(_user_line(user, idx))
    return "\n".join(lines)


def users_page_keyboard(
    users: list[User],
    *,
    page: int,
    page_size: int = PAGE_SIZE,
) -> InlineKeyboardMarkup:
    total = len(users)
    pages = max(1, (total + page_size - 1) // page_size)
    page = clamp_page(page, total, page_size)
    chunk = users[page * page_size : (page + 1) * page_size]

    rows: list[list[InlineKeyboardButton]] = []
    for user in chunk:
        if user.is_admin:
            continue
        if repo.user_has_access(user):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"❌ {user.telegram_id}",
                        callback_data=f"admin:revoke:{user.telegram_id}:{page}",
                    )
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"✅ {user.telegram_id}",
                        callback_data=f"admin:allow:{user.telegram_id}:{page}",
                    )
                ]
            )

    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text="◀️", callback_data=f"admin:users:pg:{page - 1}")
            )
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="admin:noop"))
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(text="▶️", callback_data=f"admin:users:pg:{page + 1}")
            )
        rows.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def new_user_notification_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Дать доступ",
                    callback_data=f"admin:allow:{telegram_id}:0",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"admin:dismiss:{telegram_id}",
                ),
            ]
        ]
    )
