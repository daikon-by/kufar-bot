from kufar_bot.kufar.models import AdListing
from kufar_bot.services.listing_digest import (
    build_digest_chunks,
    digest_header,
    plural_ads,
    _format_digest_line,
)
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


def test_plural_ads():
    assert plural_ads(1) == "объявление"
    assert plural_ads(2) == "объявления"
    assert plural_ads(5) == "объявлений"
    assert plural_ads(1996) == "объявлений"


def test_digest_header():
    header = digest_header(1996, "Компьютерное оборудование", "https://www.kufar.by/l/rn")
    assert "Найдено 1996 объявлений" in header
    assert "Компьютерное оборудование" in header


def test_digest_line_format():
    listing = _listing(1, "Фоторезистор ФСД-Г2")
    listing.area_label = "Столин"
    listing.region_label = "Брестская область"

    line = _format_digest_line(listing)
    assert "1467" not in line
    assert "1." not in line.split("\n")[0]
    assert "Фоторезистор" in line
    assert "50.00 BYN" in line
    assert "Столин" in line
    assert "https://www.kufar.by/item/1" in line


def test_digest_splits_long_list():
    listings = [_listing(i, f"Товар номер {i}") for i in range(1, 51)]
    header = digest_header(50, "Сад", "https://www.kufar.by/l/test")
    parts = build_digest_chunks(listings, header=header, max_length=1200)
    assert len(parts) >= 2
    assert all(len(text) <= 1200 for text, _ in parts)
    all_ids = [ad_id for _, ids in parts for ad_id in ids]
    assert all_ids == list(range(1, 51))
    assert "Товар номер 1" in parts[0][0]
    assert "Товар номер 50" in parts[-1][0]
