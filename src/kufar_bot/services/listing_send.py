from __future__ import annotations

import asyncio

import structlog
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from kufar_bot.config import settings
from kufar_bot.kufar.client import KufarClient
from kufar_bot.kufar.models import AdListing
from kufar_bot.services.listing_format import TELEGRAM_CAPTION_LIMIT, TELEGRAM_MESSAGE_LIMIT, format_listing_message
from kufar_bot.services.telegram_retry import pause_between_sends, with_flood_retry

log = structlog.get_logger(__name__)


def listing_keyboard(ad_id: int, group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ В избранное", callback_data=f"fav:add:{ad_id}:{group_id}"),
            ],
            [
                InlineKeyboardButton(
                    text="➖ В минус (глобально)",
                    callback_data=f"minus:global:{ad_id}:{group_id}",
                ),
                InlineKeyboardButton(
                    text="➖ В минус (группа)",
                    callback_data=f"minus:group:{ad_id}:{group_id}",
                ),
            ],
        ]
    )


async def _attach_keyboard(
    bot: Bot,
    *,
    chat_id: int,
    message_id: int,
    keyboard: InlineKeyboardMarkup,
) -> None:
    try:
        await with_flood_retry(
            "listing_keyboard",
            lambda: bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=keyboard,
            ),
        )
    except Exception:
        log.warning("listing_keyboard_attach_failed", chat_id=chat_id, message_id=message_id)


async def send_listing(
    bot: Bot,
    chat_id: int,
    listing: AdListing,
    group,
    *,
    client: KufarClient | None = None,
    section_label: str | None = None,
) -> bool:
    """Отправляет лот одним сообщением: фото с подписью или альбом с галереей."""
    if client is not None and settings.kufar_fetch_description:
        listing = await client.enrich_with_description(listing)
        if settings.kufar_request_delay_sec > 0:
            await asyncio.sleep(settings.kufar_request_delay_sec)

    photo_urls = listing.display_photo_urls
    text_limit = TELEGRAM_CAPTION_LIMIT if photo_urls else TELEGRAM_MESSAGE_LIMIT
    text = format_listing_message(
        listing,
        group.name,
        section_label if section_label is not None else group.section_label,
        group.region_label,
        max_length=text_limit,
        description_max_chars=settings.kufar_description_max_chars,
    )
    keyboard = listing_keyboard(listing.ad_id, group.id)

    try:
        if not photo_urls:
            await with_flood_retry(
                "send_message",
                lambda: bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                ),
            )
        elif len(photo_urls) == 1:
            await with_flood_retry(
                "send_photo",
                lambda: bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_urls[0],
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                ),
            )
        else:
            media = [
                InputMediaPhoto(
                    media=url,
                    caption=text if idx == 0 else None,
                    parse_mode="HTML",
                )
                for idx, url in enumerate(photo_urls)
            ]
            messages = await with_flood_retry(
                "send_media_group",
                lambda: bot.send_media_group(chat_id=chat_id, media=media),
            )
            await _attach_keyboard(
                bot,
                chat_id=chat_id,
                message_id=messages[-1].message_id,
                keyboard=keyboard,
            )
    except Exception:
        log.exception(
            "listing_send_failed",
            user_id=chat_id,
            ad_id=listing.ad_id,
            photos=len(photo_urls),
            has_body=bool(listing.body),
        )
        if photo_urls:
            try:
                await with_flood_retry(
                    "send_message_fallback",
                    lambda: bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    ),
                )
            except Exception:
                return False
        else:
            return False

    await pause_between_sends()

    log.info(
        "listing_sent",
        user_id=chat_id,
        ad_id=listing.ad_id,
        group_id=group.id,
        title=listing.subject,
        photos=len(photo_urls),
        has_body=bool(listing.body),
    )
    return True
