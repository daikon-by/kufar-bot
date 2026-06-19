from kufar_bot.bot.minus_list_view import (
    PAGE_SIZE,
    format_minus_group_header,
    minus_phrases_page_keyboard,
)
from kufar_bot.bot.minus_scope import group_minus_phrases
from kufar_bot.db.models import NegativePhrase, SearchGroup


def _phrase(phrase: str, *, group_id: int | None = None, group_name: str | None = None) -> NegativePhrase:
    item = NegativePhrase(id=1, user_id=1, phrase=phrase, group_id=group_id)
    if group_name is not None:
        item.group = SearchGroup(id=group_id or 0, user_id=1, name=group_name)
    return item


def test_group_minus_phrases_splits_global_and_groups():
    phrases = [
        _phrase("люстра", group_id=1, group_name="Сад"),
        _phrase("ванна", group_id=1, group_name="Сад"),
        _phrase("платье"),
    ]
    groups = group_minus_phrases(phrases)
    assert len(groups) == 2
    assert "Глобально" in groups[0][0]
    assert len(groups[0][1]) == 1
    assert "Сад" in groups[1][0]
    assert len(groups[1][1]) == 2


def test_format_minus_group_header_no_duplicate_list():
    phrases = [
        _phrase("люстра", group_id=1, group_name="Сад"),
        _phrase("ванна", group_id=1, group_name="Сад"),
    ]
    text = format_minus_group_header(phrases, page=0)
    assert "Сад" in text
    assert "люстра" not in text
    assert "ванна" not in text


def test_minus_phrases_page_keyboard_pagination():
    phrases = [_phrase(f"w{i}", group_id=1, group_name="Сад") for i in range(15)]
    kb = minus_phrases_page_keyboard(phrases, group_id=1, page=0, page_size=PAGE_SIZE)
    # 12 phrase rows + 1 nav row
    assert len(kb.inline_keyboard) == 13
    nav = kb.inline_keyboard[-1]
    assert any(btn.callback_data == "minus:pg:G1:1" for btn in nav)
