from __future__ import annotations

import pytest

from kufar_bot.kufar.filters import is_blocked_by_phrases
from kufar_bot.kufar.models import AdListing
from kufar_bot.kufar.url_parser import is_kufar_url, merge_api_query, parse_listing
from datetime import UTC, datetime


class FakePhrase:
    def __init__(self, phrase: str, group_id: int | None = None):
        self.phrase = phrase
        self.group_id = group_id


def test_is_kufar_url():
    assert is_kufar_url("https://www.kufar.by/l/bobruisk?cat=1")
    assert not is_kufar_url("https://google.com")


def test_minus_filter_global():
    phrases = [FakePhrase("платье"), FakePhrase("пальто", group_id=2)]
    assert is_blocked_by_phrases("красное платье летнее", phrases, group_id=1)
    assert not is_blocked_by_phrases("садовая лейка", phrases, group_id=1)
    assert is_blocked_by_phrases("зимнее пальто", phrases, group_id=2)


def test_merge_api_query_from_url():
    query = merge_api_query("https://www.kufar.by/l/test?cat=17010&sort=lst.d")
    assert query["cat"] == "17010"
    assert query["lang"] == "ru"
    assert query["typ"] == "sell"


def test_parse_listing_price():
    raw = {
        "ad_id": 1,
        "subject": "Тест",
        "ad_link": "https://www.kufar.by/item/1",
        "price_byn": 7000,
        "currency": "BYN",
        "list_time": "2026-06-18T10:00:00Z",
        "images": [{"path": "adim1/test.jpg"}],
        "ad_parameters": [
            {"p": "region", "vl": "Могилевская область"},
            {"p": "area", "vl": "Осиповичи"},
        ],
    }
    listing = parse_listing(raw)
    assert listing.display_price == "70.00 BYN"
    assert listing.location_label == "Осиповичи, Могилевская область"
    assert listing.photo_url.endswith("test.jpg")
    assert listing.thumb_url is not None
    assert "list_thumbs" in listing.thumb_url
