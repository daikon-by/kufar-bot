from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kufar_bot.db.models import Favorite

PAGE_SIZE = 10
_BTN_TITLE_MAX = 24


def clamp_page(page: int, total: int, page_size: int = PAGE_SIZE) -> int:
    if total <= 0:
        return 0
    pages = (total + page_size - 1) // page_size
    return max(0, min(page, pages - 1))


def _favorite_button_label(idx: int, title: str) -> str:
    short = title.strip()
    if len(short) > _BTN_TITLE_MAX:
        short = short[: _BTN_TITLE_MAX - 1] + "…"
    return f"🗑 {idx}. {short}"


def format_favorites_page(favorites: list[Favorite], *, page: int, page_size: int = PAGE_SIZE) -> str:
    total = len(favorites)
    if total == 0:
        return "<b>Избранное</b>\n<i>пусто</i>"

    page = clamp_page(page, total, page_size)
    chunk = favorites[page * page_size : (page + 1) * page_size]
    lines = ["<b>Избранное</b>"]
    if total > page_size:
        start = page * page_size + 1
        end = min((page + 1) * page_size, total)
        lines.append(f"<i>{start}–{end} из {total}</i>")
    else:
        lines.append(f"<i>{total} — нажмите 🗑 чтобы удалить</i>")

    for idx, fav in enumerate(chunk, start=page * page_size + 1):
        price = f"{fav.last_price / 100:.2f} {fav.currency}" if fav.last_price else "—"
        lines.append(f"{idx}. {html.escape(fav.title)} — {html.escape(price)}")
        lines.append(html.escape(fav.url))
    return "\n".join(lines)


def favorites_page_keyboard(
    favorites: list[Favorite],
    *,
    page: int,
    page_size: int = PAGE_SIZE,
) -> InlineKeyboardMarkup:
    total = len(favorites)
    pages = max(1, (total + page_size - 1) // page_size)
    page = clamp_page(page, total, page_size)
    chunk = favorites[page * page_size : (page + 1) * page_size]

    rows: list[list[InlineKeyboardButton]] = []
    for idx, fav in enumerate(chunk, start=page * page_size + 1):
        rows.append(
            [
                InlineKeyboardButton(
                    text=_favorite_button_label(idx, fav.title),
                    callback_data=f"fav:del:{fav.id}:{page}",
                ),
            ]
        )

    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"fav:pg:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="fav:noop"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"fav:pg:{page + 1}"))
        rows.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=rows)
