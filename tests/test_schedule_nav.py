from kufar_bot.bot.schedule_nav import is_schedule_menu_button


def test_is_schedule_menu_button():
    assert is_schedule_menu_button("✅ Вкл/Выкл расписание")
    assert is_schedule_menu_button("  🕐 Времена  ")
    assert not is_schedule_menu_button("08:00, 14:00")
