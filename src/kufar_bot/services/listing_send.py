from __future__ import annotations

import asyncio

import structlog
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kufar_bot.config import settings
from kufar_bot.kufar.client import KufarClient
from kufar_bot.kufar.models import AdListing
from kufar_bot.services.listing_format import TELEGRAM_MESSAGE_LIMIT, format_listing_message

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


async def send_listing(
    bot: Bot,
    chat_id: int,
    listing: AdListing,
    group,
    *,
    client: KufarClient | None = None,
) -> bool:
    """Отправляет лот: сначала превью, затем текст с описанием и кнопками."""
    if settings.kufar_fetch_description and not listing.body and client is not None:
        listing = await client.enrich_with_description(listing)
        if settings.kufar_request_delay_sec > 0:
            await asyncio.sleep(settings.kufar_request_delay_sec)

    text = format_listing_message(
        listing,
        group.name,
        group.section_label,
        group.region_label,
        max_length=TELEGRAM_MESSAGE_LIMIT,
        description_max_chars=settings.kufar_description_max_chars,
    )
    keyboard = listing_keyboard(listing.ad_id, group.id)

    photo = listing.display_photo_url if settings.kufar_use_thumbnail else listing.photo_url
    if photo and settings.kufar_send_photo_separate:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                parse_mode="HTML",
            )
        except Exception:
            log.warning(
                "listing_thumb_send_failed",
                user_id=chat_id,
                ad_id=listing.ad_id,
                photo=photo,
            )

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        log.exception(
            "listing_text_send_failed",
            user_id=chat_id,
            ad_id=listing.ad_id,
            has_body=bool(listing.body),
        )
        return False

    if settings.telegram_send_delay_sec > 0:
        await asyncio.sleep(settings.telegram_send_delay_sec)

    log.info(
        "listing_sent",
        user_id=chat_id,
        ad_id=listing.ad_id,
        group_id=group.id,
        title=listing.subject,
        has_body=bool(listing.body),
    )
    return True
