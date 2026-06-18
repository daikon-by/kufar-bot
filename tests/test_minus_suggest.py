from kufar_bot.kufar.minus_suggest import suggest_minus_phrases


def test_suggest_minus_phrases():
    words = suggest_minus_phrases("2 колеса диаметр 200мм")
    assert "колеса" in words
    assert "диаметр" in words
