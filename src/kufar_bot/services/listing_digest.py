from __future__ import annotations

import asyncio
import html
from collections.abc import Awaitable, Callable

import structlog
from aiogram import Bot

from kufar_bot.kufar.models import AdListing
from kufar_bot.services.listing_format import TELEGRAM_MESSAGE_LIMIT
from kufar_bot.services.telegram_retry import pause_between_sends, with_flood_retry

log = structlog.get_logger(__name__)

ChunkPart = tuple[str, list[int]]
ShouldStop = Callable[[], bool] | None


def plural_ads(count: int) -> str:
    n = abs(count) % 100
    n1 = n % 10
    if n1 == 1 and n != 11:
        return "объявление"
    if 2 <= n1 <= 4 and not (12 <= n <= 14):
        return "объявления"
    return "объявлений"


def digest_header(count: int, group_name: str, search_url: str) -> str:
    short_url = search_url if len(search_url) <= 80 else search_url[:77] + "…"
    word = plural_ads(count)
    return (
        f"📋 <b>Найдено {count} {word}</b> · {html.escape(group_name)}\n"
        f"🔗 {html.escape(short_url)}"
    )


def _format_digest_line(listing: AdListing) -> str:
    title = html.escape(listing.subject)
    price = html.escape(listing.display_price)
    location = html.escape(listing.location_label) if listing.location_label else "—"
    return f"<b>{title}</b>\n{price} · {location}\n{listing.url}"


def build_digest_chunks(
    listings: list[AdListing],
    *,
    header: str,
    max_length: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[ChunkPart]:
    if not listings:
        return []

    chunks: list[ChunkPart] = []
    current = header
    current_ids: list[int] = []

    def flush() -> None:
        nonlocal current, current_ids
        if current_ids:
            chunks.append((current, current_ids))
        current = header
        current_ids = []

    for listing in listings:
        line = _format_digest_line(listing)
        candidate = f"{current}\n\n{line}" if current else line
        if len(candidate) <= max_length:
            current = candidate
            current_ids.append(listing.ad_id)
            continue

        flush()
        single = f"{header}\n\n{line}" if header else line
        if len(single) <= max_length:
            current = single
            current_ids = [listing.ad_id]
            continue

        short_title = html.escape(listing.subject[:80])
        price = html.escape(listing.display_price)
        location = html.escape(listing.location_label) if listing.location_label else "—"
        short = f"<b>{short_title}</b>\n{price} · {location}\n{listing.url}"
        current = f"{header}\n\n{short}" if header else short
        current_ids = [listing.ad_id]

    if current_ids:
        chunks.append((current, current_ids))
    return chunks


async def send_listings_digest(
    bot: Bot,
    chat_id: int,
    listings: list[AdListing],
    *,
    group_name: str,
    search_url: str,
    should_stop: ShouldStop = None,
    on_chunk_sent: Callable[[list[int]], Awaitable[None]] | None = None,
) -> tuple[bool, bool]:
    """Returns (completed, cancelled)."""
    header = digest_header(len(listings), group_name, search_url)
    parts = build_digest_chunks(listings, header=header)
    if not parts:
        return False, False

    sent_count = 0
    cancelled = False
    try:
        for chunk_text, ad_ids in parts:
            if should_stop and should_stop():
                cancelled = True
                break
            await with_flood_retry(
                "send_digest",
                lambda chunk_text=chunk_text: bot.send_message(
                    chat_id=chat_id,
                    text=chunk_text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                ),
                should_stop=should_stop,
            )
            sent_count += len(ad_ids)
            if on_chunk_sent is not None:
                await on_chunk_sent(ad_ids)
            if not await pause_between_sends(should_stop):
                cancelled = True
                break
    except asyncio.CancelledError:
        cancelled = True
        log.info("digest_cancelled", user_id=chat_id, sent_before_cancel=sent_count)
    except Exception:
        log.exception(
            "digest_send_failed",
            user_id=chat_id,
            total=len(listings),
            sent_before_fail=sent_count,
        )
        return False, cancelled

    completed = not cancelled and sent_count > 0
    if completed:
        log.info("digest_sent", user_id=chat_id, count=len(listings), parts=len(parts))
    return completed, cancelled
