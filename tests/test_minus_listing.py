from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from kufar_bot.bot.minus_listing import edit_listing_message_by_id


@pytest.mark.asyncio
async def test_edit_listing_message_by_id_success():
    bot = AsyncMock()
    bot.edit_message_text = AsyncMock()
    ok = await edit_listing_message_by_id(
        bot,
        chat_id=1,
        message_id=42,
        text="draft",
    )
    assert ok is True
    bot.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_edit_listing_message_by_id_failure():
    bot = AsyncMock()
    bot.edit_message_text = AsyncMock(side_effect=TelegramBadRequest(method="edit", message="fail"))
    ok = await edit_listing_message_by_id(
        bot,
        chat_id=1,
        message_id=42,
        text="draft",
    )
    assert ok is False
