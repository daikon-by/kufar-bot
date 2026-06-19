from kufar_bot.bot.minus_draft import (
    draft_from_selection,
    initial_draft_state,
    selection_for_phrase,
)
from kufar_bot.kufar.minus_suggest import suggest_minus_phrases, title_words


def test_title_words():
    assert title_words("Мышь проводная") == ["мышь", "проводная"]


def test_initial_draft_state():
    words, selected, draft = initial_draft_state("Мышь проводная")
    assert words == ["мышь", "проводная"]
    assert selected == []
    assert draft == ""


def test_selection_for_phrase():
    words = ["мышь", "проводная", "игровая"]
    assert selection_for_phrase(words, "мышь проводная") == [0, 1]
    assert selection_for_phrase(words, "проводная") == [1]
    assert selection_for_phrase(words, "мышь игровая") == []


def test_suggest_includes_compound_phrases():
    suggestions = suggest_minus_phrases("Мышь проводная")
    assert "мышь проводная" in suggestions
    assert "мышь" in suggestions
    assert "проводная" in suggestions


def test_draft_from_selection_preserves_order():
    words = ["мышь", "проводная", "игровая"]
    assert draft_from_selection(words, [2, 0]) == "мышь игровая"
