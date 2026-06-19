from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from kufar_bot.db import repository as repo
from kufar_bot.db.models import NegativePhrase


def format_minus_scope(
    group_id: int | None,
    group_name: str | None = None,
    *,
    for_action: bool = False,
) -> str:
    if group_id is None:
        return "глобально"
    label = f"«{group_name}»" if group_name else f"#{group_id}"
    if for_action:
        return f"для группы {label}"
    return f"группа {label}"


def minus_scope_from_phrase(item: NegativePhrase, *, for_action: bool = False) -> str:
    name = item.group.name if item.group else None
    return format_minus_scope(item.group_id, name, for_action=for_action)


async def minus_scope_label(
    session: AsyncSession,
    user_id: int,
    group_id: int | None,
    *,
    for_action: bool = False,
) -> str:
    if group_id is None:
        return "глобально"
    group = await repo.get_group(session, group_id, user_id)
    return format_minus_scope(group_id, group.name if group else None, for_action=for_action)


def minus_phrase_group_title(item: NegativePhrase | None, *, group_id: int | None = None) -> str:
    if group_id is None and (item is None or item.group_id is None):
        return "⛔ <b>Глобально</b>"
    if item is not None and item.group:
        return f"⛔ <b>Группа «{item.group.name}»</b>"
    if item is not None and item.group_id is not None:
        return f"⛔ <b>Группа #{item.group_id}</b>"
    return "⛔ <b>Группа</b>"


def group_minus_phrases(phrases: list[NegativePhrase]) -> list[tuple[str, list[NegativePhrase]]]:
    global_items = [p for p in phrases if p.group_id is None]
    by_group: dict[int, list[NegativePhrase]] = {}
    for item in phrases:
        if item.group_id is None:
            continue
        by_group.setdefault(item.group_id, []).append(item)

    groups: list[tuple[str, list[NegativePhrase]]] = []
    if global_items:
        groups.append((minus_phrase_group_title(global_items[0]), global_items))
    for group_id in sorted(
        by_group,
        key=lambda gid: (by_group[gid][0].group.name if by_group[gid][0].group else "").casefold(),
    ):
        items = by_group[group_id]
        groups.append((minus_phrase_group_title(items[0]), items))
    return groups
