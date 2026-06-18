from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from kufar_bot.kufar.models import AdListing

KUFAR_HOSTS = {"www.kufar.by", "kufar.by"}
SEARCH_API = "https://api.kufar.by/search-api/v2/search/rendered-paginated"
IMAGE_GALLERY_BASE = "https://rms.kufar.by/v1/gallery/"
IMAGE_THUMB_BASE = "https://rms.kufar.by/v1/list_thumbs_2x/"


def is_kufar_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.netloc.lower() in KUFAR_HOSTS and parsed.path.startswith("/l/")


def _extract_next_data(html: str) -> dict[str, Any] | None:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return None
    return json.loads(match.group(1))


def _merge_location(query: dict[str, str], location: dict[str, Any]) -> dict[str, str]:
    region = location.get("region") or {}
    if isinstance(region, dict) and region.get("v"):
        query.setdefault("rgn", str(region["v"]))
    areas = location.get("areas") or []
    if areas and isinstance(areas[0], dict) and areas[0].get("v"):
        query.setdefault("ar", str(areas[0]["v"]))
    return query


def query_from_url(url: str) -> dict[str, str]:
    parsed = urlparse(url.strip())
    query: dict[str, str] = {}
    for key, values in parse_qs(parsed.query).items():
        if values:
            query[key] = values[0]
    return query


def query_from_page(html: str) -> dict[str, str]:
    data = _extract_next_data(html)
    if not data:
        return {}
    state = data.get("props", {}).get("initialState", {})
    router = state.get("router", {})
    query_for_be = router.get("queryForBe") or router.get("query") or {}
    result = {str(k): str(v) for k, v in query_for_be.items() if v is not None}
    location = state.get("location", {})
    if isinstance(location, dict):
        result = _merge_location(result, location)
    filters = state.get("filters", {})
    if isinstance(filters, dict):
        filter_query = filters.get("query") or {}
        if isinstance(filter_query, dict):
            for key, value in filter_query.items():
                if value is not None and key not in result:
                    result[str(key)] = str(value)
    return result


def merge_api_query(url: str, page_html: str | None = None) -> dict[str, str]:
    query = query_from_url(url)
    if page_html:
        page_query = query_from_page(page_html)
        for key, value in page_query.items():
            query.setdefault(key, value)
    query.setdefault("lang", "ru")
    query.setdefault("typ", "sell")
    query.setdefault("sort", "lst.d")
    return query


def api_query_to_params(query: dict[str, str], *, size: int = 30, cursor: str | None = None) -> dict[str, str]:
    params = dict(query)
    params["size"] = str(size)
    if cursor:
        params["cursor"] = cursor
    return params


def build_search_url(params: dict[str, str]) -> str:
    return f"{SEARCH_API}?{urlencode(params)}"


def _ad_param_value(raw: dict[str, Any], param: str) -> str | None:
    for item in raw.get("ad_parameters") or []:
        if isinstance(item, dict) and item.get("p") == param:
            value = item.get("vl")
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def parse_listing(raw: dict[str, Any]) -> AdListing:
    list_time_raw = raw.get("list_time")
    if isinstance(list_time_raw, str):
        list_time = datetime.fromisoformat(list_time_raw.replace("Z", "+00:00"))
    else:
        list_time = datetime.now(UTC)

    images = raw.get("images") or []
    photo_url = None
    thumb_url = None
    if images and isinstance(images[0], dict) and images[0].get("path"):
        path = images[0]["path"]
        photo_url = IMAGE_GALLERY_BASE + path
        thumb_url = IMAGE_THUMB_BASE + path

    price_byn = raw.get("price_byn")
    price_usd = raw.get("price_usd")
    if isinstance(price_byn, str):
        price_byn = int(price_byn)
    if isinstance(price_usd, str):
        price_usd = int(price_usd)

    return AdListing(
        ad_id=int(raw["ad_id"]),
        subject=str(raw.get("subject") or "Без названия"),
        url=str(raw.get("ad_link") or f"https://www.kufar.by/item/{raw['ad_id']}"),
        price_byn=price_byn,
        price_usd=price_usd,
        currency=str(raw.get("currency") or "BYN"),
        list_time=list_time,
        body=raw.get("body") or raw.get("body_short"),
        photo_url=photo_url,
        thumb_url=thumb_url,
        area_label=_ad_param_value(raw, "area"),
        region_label=_ad_param_value(raw, "region"),
    )


def parse_ad_from_item_page(html: str) -> AdListing | None:
    data = _extract_next_data(html)
    if not data:
        return None

    def find_ad(obj: Any) -> dict[str, Any] | None:
        if isinstance(obj, dict) and "ad_id" in obj and "subject" in obj:
            return obj
        if isinstance(obj, dict):
            for value in obj.values():
                found = find_ad(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = find_ad(item)
                if found:
                    return found
        return None

    ad = find_ad(data)
    if not ad:
        return None
    return parse_listing(ad)
