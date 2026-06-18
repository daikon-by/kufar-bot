from kufar_bot.kufar.models import AdListing
from kufar_bot.services.listing_digest import build_digest_chunks
from datetime import UTC, datetime


def _listing(ad_id: int, subject: str) -> AdListing:
    return AdListing(
        ad_id=ad_id,
        subject=subject,
        url=f"https://www.kufar.by/item/{ad_id}",
        price_byn=5000,
        price_usd=None,
        currency="BYN",
        list_time=datetime(2026, 6, 18, 12, 0, tzinfo=UTC),
        body=None,
        photo_url=None,
        thumb_url=None,
    )


def test_digest_splits_long_list():
    listings = [_listing(i, f"Товар номер {i}") for i in range(1, 51)]
    header = "📋 <b>Новые объявления (50)</b> — Сад"
    chunks = build_digest_chunks(listings, header=header, max_length=1200)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 1200 for chunk in chunks)
    assert "Товар номер 1" in chunks[0]
    assert "Товар номер 50" in chunks[-1]
