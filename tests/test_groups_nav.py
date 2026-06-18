from kufar_bot.bot.groups_nav import is_groups_menu_button


def test_is_groups_menu_button():
    assert is_groups_menu_button("📋 Список групп")
    assert is_groups_menu_button("  📋 Список групп  ")
    assert not is_groups_menu_button("https://www.kufar.by/l/test")
    assert not is_groups_menu_button(None)
