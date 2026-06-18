from __future__ import annotations

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message

from kufar_bot.services.listing_send import listing_keyboard

log = structlog.get_logger(__name__)


def listing_message_snapshot(message: Message) -> dict:
    return {
        "listing_message_id": message.message_id,
        "listing_chat_id": message.chat.id,
        "listing_text": message.html_text or message.text or "",
    }


async def restore_listing_message(
    bot: Bot,
    *,
    chat_id: int,
    message_id: int,
    text: str,
    ad_id: int,
    group_id: int,
) -> bool:
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=listing_keyboard(ad_id, group_id),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except TelegramBadRequest as exc:
        log.warning(
            "listing_restore_failed",
            chat_id=chat_id,
            message_id=message_id,
            error=str(exc),
        )
        return False


async def edit_listing_message(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except TelegramBadRequest as exc:
        log.warning("listing_edit_failed", message_id=message.message_id, error=str(exc))
        return False
