from __future__ import annotations

import re


def suggest_minus_phrases(title: str, *, limit: int = 6) -> list[str]:
    """Подсказки из заголовка объявления."""
    words = re.findall(r"[\wёЁа-яА-ЯіІўЎ]+", title.lower())
    seen: set[str] = set()
    result: list[str] = []
    for word in words:
        if len(word) < 3 or word in seen:
            continue
        seen.add(word)
        result.append(word)
        if len(result) >= limit:
            break
    if not result and title.strip():
        result.append(title.strip().lower()[:40])
    return result
