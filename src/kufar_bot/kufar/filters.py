from __future__ import annotations

from kufar_bot.db.models import NegativePhrase


def matches_negative_phrase(text: str, phrase: str) -> bool:
    return phrase.strip().lower() in text.lower()


def is_blocked_by_phrases(
    text: str,
    phrases: list[NegativePhrase],
    *,
    group_id: int | None = None,
) -> bool:
    normalized = text.lower()
    for item in phrases:
        if item.group_id is not None and item.group_id != group_id:
            continue
        if matches_negative_phrase(normalized, item.phrase):
            return True
    return False


def filter_phrases_for_group(
    phrases: list[NegativePhrase],
    group_id: int,
) -> list[NegativePhrase]:
    return [p for p in phrases if p.group_id is None or p.group_id == group_id]
