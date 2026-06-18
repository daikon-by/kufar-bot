from kufar_bot.kufar.models import AdListing
from kufar_bot.services.listing_format import format_listing_message
from datetime import UTC, datetime


def _listing(body: str | None = None) -> AdListing:
    return AdListing(
        ad_id=1,
        subject="Тест",
        url="https://www.kufar.by/item/1",
        price_byn=1500,
        price_usd=None,
        currency="BYN",
        list_time=datetime(2026, 6, 18, 12, 0, tzinfo=UTC),
        body=body,
        photo_url="https://example.com/a.jpg",
    )


def test_message_includes_description_and_city():
    listing = _listing("Колёса в хорошем состоянии")
    listing = AdListing(
        ad_id=listing.ad_id,
        subject=listing.subject,
        url=listing.url,
        price_byn=listing.price_byn,
        price_usd=listing.price_usd,
        currency=listing.currency,
        list_time=listing.list_time,
        body=listing.body,
        photo_url=listing.photo_url,
        area_label="Бобруйск",
        region_label="Могилевская область",
    )
    text = format_listing_message(
        listing,
        "Сад",
        "Огород",
        "Могилёв",
        max_length=1024,
    )
    assert "📝" in text
    assert "Колёса" in text
    assert "🏙" in text
    assert "Бобруйск" in text


def test_message_truncates_long_description():
    text = format_listing_message(
        _listing("а" * 2000),
        "Сад",
        "",
        "",
        max_length=1024,
        description_max_chars=100,
    )
    assert len(text) <= 1024
    assert "…" in text
