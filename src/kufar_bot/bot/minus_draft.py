from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kufar_bot.kufar.minus_suggest import suggest_minus_phrases, title_words


def draft_from_selection(words: list[str], selected: list[int]) -> str:
    return " ".join(words[i] for i in sorted(selected))


def initial_draft_state(subject: str) -> tuple[list[str], list[int], str]:
    words = title_words(subject)
    return words, [], ""


def selection_for_phrase(words: list[str], phrase: str) -> list[int]:
    phrase_words = title_words(phrase)
    if not phrase_words or not words:
        return []
    for start in range(len(words) - len(phrase_words) + 1):
        if words[start : start + len(phrase_words)] == phrase_words:
            return list(range(start, start + len(phrase_words)))
    return []


def format_minus_draft_prompt(
    scope: str,
    subject: str,
    draft: str,
    *,
    manual: bool = False,
) -> str:
    draft_line = html.escape(draft) if draft else "—"
    hint = (
        "Отправьте другой текст или нажмите «Сохранить»."
        if manual
        else "Нажмите слова ниже, чтобы собрать фразу, или отправьте свой текст."
    )
    return (
        f"⛔ <b>Минус-фраза</b> ({scope})\n\n"
        f"Заголовок: {html.escape(subject)}\n\n"
        f"Черновик:\n<code>{draft_line}</code>\n\n"
        f"{hint}"
    )


def minus_draft_keyboard(
    words: list[str],
    selected: list[int],
    suggestions: list[str],
    draft: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    selected_set = set(selected)

    quick_row: list[InlineKeyboardButton] = []
    for idx, phrase in enumerate(suggestions):
        if phrase == draft:
            continue
        label = phrase if len(phrase) <= 24 else phrase[:21] + "…"
        quick_row.append(InlineKeyboardButton(text=f"💡 {label}", callback_data=f"minus:hint:{idx}"))
        if len(quick_row) == 2:
            rows.append(quick_row)
            quick_row = []
    if quick_row:
        rows.append(quick_row)

    word_row: list[InlineKeyboardButton] = []
    for idx, word in enumerate(words):
        mark = "✓ " if idx in selected_set else ""
        label = f"{mark}{word}" if len(word) <= 22 else f"{mark}{word[:19]}…"
        word_row.append(InlineKeyboardButton(text=label, callback_data=f"minus:wd:{idx}"))
        if len(word_row) == 2:
            rows.append(word_row)
            word_row = []
    if word_row:
        rows.append(word_row)

    if len(words) > 1:
        rows.append(
            [InlineKeyboardButton(text="📋 Весь заголовок", callback_data="minus:wd:all")]
        )

    rows.append(
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data="minus:save"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="minus:cancel"),
        ]
    )
    rows.append([InlineKeyboardButton(text="↩️ К объявлению", callback_data="minus:back_listing")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def minus_draft_payload(
    scope: str,
    subject: str,
    draft: str,
    words: list[str],
    selected: list[int],
    suggestions: list[str],
    *,
    manual: bool = False,
) -> tuple[str, InlineKeyboardMarkup]:
    text = format_minus_draft_prompt(scope, subject, draft, manual=manual)
    markup = minus_draft_keyboard(words, selected, suggestions, draft)
    return text, markup
