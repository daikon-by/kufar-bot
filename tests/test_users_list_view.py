from datetime import UTC, datetime

from kufar_bot.bot.users_list_view import format_users_page, users_page_keyboard
from kufar_bot.db.models import User


def _user(telegram_id: int, *, authorized: bool = False, admin: bool = False) -> User:
    return User(
        telegram_id=telegram_id,
        username=f"user{telegram_id}",
        is_authorized=authorized,
        is_admin=admin,
        created_at=datetime.now(UTC),
    )


def test_format_users_page_empty():
    text = format_users_page([], page=0)
    assert "Пользователи" in text
    assert "никого нет" in text


def test_users_page_keyboard_allow_and_revoke():
    users = [
        _user(1, authorized=True),
        _user(2, authorized=False),
        _user(3, authorized=True, admin=True),
    ]
    markup = users_page_keyboard(users, page=0)
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "admin:revoke:1:0" in callbacks
    assert "admin:allow:2:0" in callbacks
    assert not any("admin:revoke:3" in cb for cb in callbacks)
