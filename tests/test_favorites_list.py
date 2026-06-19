from datetime import UTC, datetime

from kufar_bot.bot.favorites_list_view import favorites_page_keyboard, format_favorites_page
from kufar_bot.db.models import Favorite


def _favorite(id: int, title: str) -> Favorite:
    return Favorite(
        id=id,
        user_id=1,
        ad_id=1000 + id,
        title=title,
        url=f"https://www.kufar.by/item/{id}",
        photo_url=None,
        last_price=10000,
        currency="BYN",
        is_active=True,
        added_at=datetime.now(UTC),
    )


def test_favorites_page_keyboard_callback_data_within_limit():
    favorites = [_favorite(i, f"Товар номер {i}") for i in range(1, 12)]
    keyboard = favorites_page_keyboard(favorites, page=0)
    for row in keyboard.inline_keyboard:
        for button in row:
            assert len(button.callback_data.encode("utf-8")) <= 64


def test_format_favorites_page_shows_range():
    favorites = [_favorite(i, f"Item {i}") for i in range(1, 13)]
    text = format_favorites_page(favorites, page=1)
    assert "11–12 из 12" in text
    assert "Item 11" in text
