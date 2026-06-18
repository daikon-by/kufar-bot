"""Кнопки меню расписания — при нажатии во время FSM нужно выходить из состояния."""

SCHEDULE_MENU_BUTTONS: tuple[str, ...] = (
    "🕐 Времена",
    "📅 Дни недели",
    "✅ Вкл/Выкл расписание",
    "📋 Текущее",
    "◀️ Назад",
    "⏰ Расписание",
)


def is_schedule_menu_button(text: str | None) -> bool:
    if not text:
        return False
    return text.strip() in SCHEDULE_MENU_BUTTONS
