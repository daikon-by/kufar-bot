from __future__ import annotations

import re


def title_words(title: str) -> list[str]:
    words = re.findall(r"[\wёЁа-яА-ЯіІўЎ]+", title.lower())
    seen: set[str] = set()
    result: list[str] = []
    for word in words:
        if len(word) < 2 or word in seen:
            continue
        seen.add(word)
        result.append(word)
    return result


def suggest_minus_phrases(title: str, *, limit: int = 6) -> list[str]:
    """Подсказки из заголовка: целиком, пары слов, отдельные слова."""
    words = title_words(title)
    seen: set[str] = set()
    result: list[str] = []

    def add(phrase: str) -> None:
        normalized = phrase.strip().lower()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        result.append(normalized)

    if words:
        add(" ".join(words))
        for idx in range(len(words) - 1):
            add(f"{words[idx]} {words[idx + 1]}")
    for word in words:
        if len(word) >= 3:
            add(word)

    if not result and title.strip():
        add(title.strip().lower()[:40])
    return result[:limit]
