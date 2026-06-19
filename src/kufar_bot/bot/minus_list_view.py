from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kufar_bot.bot.minus_scope import minus_phrase_group_title
from kufar_bot.db.models import NegativePhrase

PAGE_SIZE = 12
_BTN_PHRASE_MAX = 26


def minus_scope_key(group_id: int | None) -> str:
    return "g" if group_id is None else f"G{group_id}"


def parse_minus_scope_key(key: str) -> int | None:
    if key == "g":
        return None
    if key.startswith("G") and key[1:].isdigit():
        return int(key[1:])
    return None


def _phrase_button_label(phrase: str) -> str:
    if len(phrase) <= _BTN_PHRASE_MAX:
        return phrase
    return phrase[: _BTN_PHRASE_MAX - 1] + "…"


def format_minus_group_header(
    phrases: list[NegativePhrase],
    *,
    page: int,
    page_size: int = PAGE_SIZE,
) -> str:
    sample = phrases[0] if phrases else None
    group_id = sample.group_id if sample else None
    title = minus_phrase_group_title(sample, group_id=group_id)
    total = len(phrases)
    if total == 0:
        return f"{title}\n<i>фраз нет</i>"
    if total <= page_size:
        return f"{title}\n<i>{total} фраз — нажмите ✏️ или 🗑</i>"
    pages = (total + page_size - 1) // page_size
    page = max(0, min(page, pages - 1))
    start = page * page_size + 1
    end = min((page + 1) * page_size, total)
    return f"{title}\n<i>фразы {start}–{end} из {total}</i>"


def minus_phrases_page_keyboard(
    phrases: list[NegativePhrase],
    *,
    group_id: int | None,
    page: int,
    page_size: int = PAGE_SIZE,
) -> InlineKeyboardMarkup:
    scope = minus_scope_key(group_id)
    total = len(phrases)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    chunk = phrases[page * page_size : (page + 1) * page_size]

    rows: list[list[InlineKeyboardButton]] = []
    for item in chunk:
        label = _phrase_button_label(item.phrase)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✏️ {label}",
                    callback_data=f"minus:edit:{item.id}",
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=f"minus:del:{item.id}:{scope}:{page}",
                ),
            ]
        )

    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text="◀️", callback_data=f"minus:pg:{scope}:{page - 1}")
            )
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="minus:noop"))
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(text="▶️", callback_data=f"minus:pg:{scope}:{page + 1}")
            )
        rows.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def clamp_page(page: int, total: int, page_size: int = PAGE_SIZE) -> int:
    if total <= 0:
        return 0
    pages = max(1, (total + page_size - 1) // page_size)
    return max(0, min(page, pages - 1))
