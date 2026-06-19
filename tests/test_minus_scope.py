from kufar_bot.bot.minus_scope import format_minus_scope


def test_format_minus_scope_global():
    assert format_minus_scope(None) == "глобально"


def test_format_minus_scope_named_group():
    assert format_minus_scope(1, "Сад") == "группа «Сад»"


def test_format_minus_scope_for_action():
    assert format_minus_scope(1, "Сад", for_action=True) == "для группы «Сад»"


def test_format_minus_scope_missing_name_fallback():
    assert format_minus_scope(3, None) == "группа #3"
