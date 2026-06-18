from __future__ import annotations

import html
import re

from kufar_bot.kufar.models import AdListing

TELEGRAM_CAPTION_LIMIT = 1024
TELEGRAM_MESSAGE_LIMIT = 4096


def _clean_body(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    return html.escape(cleaned)


def format_listing_message(
    listing: AdListing,
    group_name: str,
    section: str,
    region: str,
    *,
    max_length: int = TELEGRAM_MESSAGE_LIMIT,
    description_max_chars: int = 600,
) -> str:
    header_lines = [
        f"<b>{html.escape(listing.subject)}</b>",
        f"💰 {listing.display_price}",
    ]
    if listing.location_label:
        header_lines.append(f"🏙 {html.escape(listing.location_label)}")
    if listing.body:
        body = _clean_body(listing.body)
        if len(body) > description_max_chars:
            body = body[: description_max_chars - 1] + "…"
        header_lines.append(f"📝 {body}")

    footer_lines = [f"📁 {html.escape(group_name)}"]
    if section:
        footer_lines.append(f"🏷 {html.escape(section)}")
    if region:
        footer_lines.append(f"📍 {html.escape(region)}")
    footer_lines.append(f"🕒 {listing.list_time.astimezone().strftime('%d.%m.%Y %H:%M')}")
    footer_lines.append(f'<a href="{listing.url}">Открыть на Kufar</a>')

    footer = "\n".join(footer_lines)
    header = "\n".join(header_lines)

    if len(header) + len(footer) + 1 <= max_length:
        return f"{header}\n{footer}"

    # Ужимаем описание, чтобы влезло в лимит Telegram
    if listing.body:
        body_idx = next((i for i, line in enumerate(header_lines) if line.startswith("📝")), None)
        if body_idx is not None:
            fixed_len = sum(len(line) + 1 for i, line in enumerate(header_lines) if i != body_idx)
            budget = max_length - len(footer) - fixed_len - 1
            if budget > 40:
                short_body = _clean_body(listing.body)
                if len(short_body) > budget:
                    short_body = short_body[: budget - 1] + "…"
                header_lines[body_idx] = f"📝 {short_body}"
                header = "\n".join(header_lines)
                if len(header) + len(footer) + 1 <= max_length:
                    return f"{header}\n{footer}"
        header = "\n".join(line for line in header_lines if not line.startswith("📝"))

    return f"{header}\n{footer}"
