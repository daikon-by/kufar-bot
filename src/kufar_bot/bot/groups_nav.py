"""Кнопки меню групп — при нажатии во время FSM нужно выходить из состояния."""

GROUPS_MENU_BUTTONS: tuple[str, ...] = (
    "➕ Добавить группу",
    "📋 Список групп",
    "🔗 Мои ссылки",
    "◀️ Назад",
    "📁 Группы",
)


def is_groups_menu_button(text: str | None) -> bool:
    if not text:
        return False
    return text.strip() in GROUPS_MENU_BUTTONS
