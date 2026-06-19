from kufar_bot.bot.group_display import build_group_view, format_group_urls, group_urls_keyboard
from kufar_bot.db.models import SearchGroup, SearchUrl


def test_build_group_view_single_message_with_sections():
    group = SearchGroup(id=1, user_id=1, name="Дом и сад", region_label="Бобруйский район")
    group.urls = [
        SearchUrl(id=1, group_id=1, url="https://www.kufar.by/l/a", section_label="Сад и огород"),
        SearchUrl(id=2, group_id=1, url="https://www.kufar.by/l/b", section_label="Все для дома"),
    ]
    view = build_group_view(group)
    text = format_group_urls(view)
    assert text.count("Дом и сад") == 1
    assert "Сад и огород" in text
    assert "Все для дома" in text
    assert len(view.sections) == 2


def test_group_urls_keyboard_callback_data_within_telegram_limit():
    group = SearchGroup(id=1, user_id=1, name="Дом и сад", region_label="Бобруйский район")
    group.urls = [
        SearchUrl(id=1, group_id=1, url="https://www.kufar.by/l/a", section_label="Сад и огород"),
        SearchUrl(id=2, group_id=1, url="https://www.kufar.by/l/b", section_label="Все для дома"),
        SearchUrl(id=3, group_id=1, url="https://www.kufar.by/l/c", section_label="Ремонт и стройка"),
    ]
    view = build_group_view(group)
    keyboard = group_urls_keyboard(view)
    for row in keyboard.inline_keyboard:
        for button in row:
            assert len(button.callback_data.encode("utf-8")) <= 64


def test_group_urls_keyboard_no_section_reset_when_one_url_per_section():
    group = SearchGroup(id=1, user_id=1, name="Дом и сад", region_label="")
    group.urls = [
        SearchUrl(id=1, group_id=1, url="https://www.kufar.by/l/a", section_label="Сад и огород"),
        SearchUrl(id=2, group_id=1, url="https://www.kufar.by/l/b", section_label="Все для дома"),
    ]
    view = build_group_view(group)
    keyboard = group_urls_keyboard(view)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert not any(text.startswith("🔄 Раздел") for text in labels)


def test_group_urls_keyboard_section_reset_when_multiple_urls_in_section():
    group = SearchGroup(id=1, user_id=1, name="Дом и сад", region_label="")
    group.urls = [
        SearchUrl(id=1, group_id=1, url="https://www.kufar.by/l/a", section_label="Сад и огород"),
        SearchUrl(id=2, group_id=1, url="https://www.kufar.by/l/b", section_label="Сад и огород"),
    ]
    view = build_group_view(group)
    keyboard = group_urls_keyboard(view)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert any(text == "🔄 Раздел «Сад и огород»" for text in labels)
