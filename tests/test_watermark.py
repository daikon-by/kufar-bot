from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kufar_bot.kufar.client import KufarClient


def _ad(ad_id: int, minutes: int) -> dict:
    return {
        "ad_id": ad_id,
        "subject": f"Ad {ad_id}",
        "ad_link": f"https://www.kufar.by/item/{ad_id}",
        "price_byn": 1000,
        "currency": "BYN",
        "list_time": f"2026-06-18T12:{minutes:02d}:00Z",
        "images": [],
    }


@pytest.mark.asyncio
async def test_collect_stops_at_watermark():
    pages = [
        {"ads": [_ad(10, 0), _ad(9, 1)], "pagination": {"pages": [{"label": "next", "token": "c2"}]}},
        {"ads": [_ad(8, 2), _ad(5, 3)], "pagination": {"pages": []}},
    ]
    client = KufarClient()
    mock_session = AsyncMock()

    async def fake_get(url, params=None, timeout=30):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = pages.pop(0)
        return response

    mock_session.get = fake_get
    client._session = mock_session

    listings, found = await client.collect_since_watermark({"cat": "1"}, watermark_ad_id=5)

    assert found is True
    assert [item.ad_id for item in listings] == [10, 9, 8]


@pytest.mark.asyncio
async def test_collect_stops_at_since_without_watermark():
    since = datetime(2026, 6, 18, 12, 0, 30, tzinfo=UTC)
    pages = [
        {"ads": [_ad(10, 2), _ad(9, 1), _ad(8, 0)], "pagination": {"pages": []}},
    ]
    client = KufarClient()
    mock_session = AsyncMock()

    async def fake_get(url, params=None, timeout=30):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = pages.pop(0)
        return response

    mock_session.get = fake_get
    client._session = mock_session

    listings, found = await client.collect_since_watermark({"cat": "1"}, since=since)

    assert found is True
    assert [item.ad_id for item in listings] == [10, 9]
