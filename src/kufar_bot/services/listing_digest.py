from __future__ import annotations

import html

import structlog
from aiogram import Bot

from kufar_bot.kufar.models import AdListing
from kufar_bot.services.listing_format import TELEGRAM_MESSAGE_LIMIT

log = structlog.get_logger(__name__)


def _format_digest_line(index: int, listing: AdListing) -> str:
    title = html.escape(listing.subject)
    location = html.escape(listing.location_label) if listing.location_label else ""
    location_part = f"{location} · " if location else ""
    return f"{index}. {listing.display_price} · {location_part}{title}\n{listing.url}"


def build_digest_chunks(
    listings: list[AdListing],
    *,
    header: str,
    max_length: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[str]:
    if not listings:
        return []

    chunks: list[str] = []
    current = header
    for index, listing in enumerate(listings, start=1):
        line = _format_digest_line(index, listing)
        candidate = f"{current}\n\n{line}" if current else line
        if len(candidate) <= max_length:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = f"{header}\n\n{line}" if len(f"{header}\n\n{line}") <= max_length else line
        if len(current) > max_length:
            short = f"{index}. {listing.display_price} — {html.escape(listing.subject[:80])}\n{listing.url}"
            current = f"{header}\n\n{short}" if chunks else short

    if current:
        chunks.append(current)
    return chunks


async def send_listings_digest(
    bot: Bot,
    chat_id: int,
    listings: list[AdListing],
    *,
    group_name: str,
    search_url: str,
) -> bool:
    short_url = search_url if len(search_url) <= 80 else search_url[:77] + "…"
    header = (
        f"📋 <b>Новые объявления ({len(listings)})</b> — {html.escape(group_name)}\n"
        f"🔗 {html.escape(short_url)}"
    )
    chunks = build_digest_chunks(listings, header=header)
    if not chunks:
        return False

    try:
        for chunk in chunks:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    except Exception:
        log.exception("digest_send_failed", user_id=chat_id, count=len(listings))
        return False

    log.info("digest_sent", user_id=chat_id, count=len(listings), parts=len(chunks))
    return True
