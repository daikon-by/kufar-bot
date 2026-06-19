from __future__ import annotations

import html
from dataclasses import dataclass, field
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kufar_bot.db.models import SearchGroup, SearchUrl
from kufar_bot.kufar.url_parser import short_kufar_list_url


@dataclass(slots=True)
class GroupView:
    group_id: int
    name: str
    region_label: str
    urls: list[SearchUrl] = field(default_factory=list)

    @property
    def sections(self) -> list[str]:
        seen: list[str] = []
        for item in self.urls:
            label = (item.section_label or "").strip()
            if label and label not in seen:
                seen.append(label)
        return seen


def build_group_view(group: SearchGroup) -> GroupView:
    urls = sorted(
        group.urls,
        key=lambda item: ((item.section_label or "").casefold(), item.id),
    )
    return GroupView(
        group_id=group.id,
        name=group.name,
        region_label=group.region_label or "",
        urls=urls,
    )


def format_group_summary(view: GroupView) -> str:
    lines = [f"<b>{html.escape(view.name)}</b>"]
    if view.sections:
        label = "Раздел" if len(view.sections) == 1 else "Разделы"
        lines.append(f"{label}: {', '.join(html.escape(s) for s in view.sections)}")
    lines.append(f"Регион: {html.escape(view.region_label or '—')}")
    lines.append(f"Ссылок: {len(view.urls)}")
    return "\n".join(lines)


def format_group_urls(view: GroupView) -> str:
    lines = [f"<b>{html.escape(view.name)}</b>"]
    if view.region_label:
        lines.append(f"Регион: {html.escape(view.region_label)}")
    if not view.urls:
        lines.append("Ссылок нет.")
        return "\n".join(lines)

    multi_section = len(view.sections) > 1
    for idx, item in enumerate(view.urls, start=1):
        label = html.escape(short_kufar_list_url(item.url))
        safe_url = html.escape(item.url, quote=True)
        section = (item.section_label or "").strip()
        if multi_section and section:
            lines.append(f"{idx}. <i>{html.escape(section)}</i>")
            lines.append(f'<a href="{safe_url}">{label}</a>')
        else:
            lines.append(f'{idx}. <a href="{safe_url}">{label}</a>')
    return "\n".join(lines)


def _section_url_counts(view: GroupView) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in view.urls:
        label = (item.section_label or "").strip()
        if label:
            counts[label] = counts.get(label, 0) + 1
    return counts


def group_urls_keyboard(view: GroupView) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    multi_section = len(view.sections) > 1

    for idx, item in enumerate(view.urls, start=1):
        section = (item.section_label or "").strip()
        prefix = f"{idx}."
        if multi_section and section:
            short = section if len(section) <= 12 else section[:9] + "…"
            prefix = f"{idx}. {short}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix} 🔄",
                    callback_data=f"group:url:reset:{item.id}:{view.group_id}",
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=f"group:url:del:{item.id}:{view.group_id}",
                ),
            ]
        )

    section_counts = _section_url_counts(view)
    for idx, section in enumerate(view.sections):
        if section_counts.get(section, 0) <= 1:
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🔄 Раздел «{section}»",
                    callback_data=f"group:sec:reset:{view.group_id}:{idx}",
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Раздел",
                callback_data=f"group:section:add:{view.group_id}",
            ),
            InlineKeyboardButton(
                text="➕ Ссылка",
                callback_data=f"group:url:add:{view.group_id}",
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="🔄 Сбросить опрос (вся группа)",
                callback_data=f"group:reset_poll:{view.group_id}",
            ),
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"group:del:{view.group_id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def group_list_keyboard(view: GroupView) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Ссылки", callback_data=f"group:urls:{view.group_id}")],
            [
                InlineKeyboardButton(
                    text="➕ Раздел",
                    callback_data=f"group:section:add:{view.group_id}",
                ),
                InlineKeyboardButton(
                    text="➕ Ссылка",
                    callback_data=f"group:url:add:{view.group_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Сбросить опрос",
                    callback_data=f"group:reset_poll:{view.group_id}",
                ),
            ],
            [InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"group:del:{view.group_id}")],
        ]
    )


def url_label(view: GroupView, url_id: int) -> str:
    for idx, item in enumerate(view.urls, start=1):
        if item.id == url_id:
            section = (item.section_label or "").strip()
            if section:
                return f"ссылка {idx} ({section})"
            return f"ссылка {idx}"
    return "ссылка"


