from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import structlog
from curl_cffi.requests import AsyncSession

from kufar_bot.config import settings
from kufar_bot.kufar.models import AdListing
from kufar_bot.kufar.url_parser import (
    SEARCH_API,
    api_query_to_params,
    merge_api_query,
    parse_ad_from_item_page,
    parse_listing,
)

log = structlog.get_logger(__name__)


class KufarClient:
    def __init__(self) -> None:
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> KufarClient:
        self._session = AsyncSession(impersonate=settings.kufar_impersonate)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("KufarClient is not started")
        return self._session

    async def fetch_text(self, url: str) -> str:
        log.debug("http_get", url=url)
        response = await self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    async def resolve_search_query(self, url: str) -> dict[str, str]:
        page_html = None
        try:
            page_html = await self.fetch_text(url)
            log.info("url_resolved_page_ok", url=url)
        except Exception as exc:
            log.warning("page_fetch_failed", url=url, error=str(exc))
        query = merge_api_query(url, page_html)
        log.info("url_resolved_query", url=url, query=query)
        return query

    async def search_listings(
        self,
        api_query: dict[str, str] | str,
        *,
        since: datetime | None = None,
        max_pages: int = 3,
    ) -> list[AdListing]:
        if isinstance(api_query, str):
            query = json.loads(api_query)
        else:
            query = dict(api_query)

        listings: list[AdListing] = []
        cursor: str | None = None

        for page in range(max_pages):
            params = api_query_to_params(query, cursor=cursor)
            log.debug("kufar_search_request", page=page + 1, params=params)
            response = await self.session.get(SEARCH_API, params=params, timeout=30)
            if response.status_code != 200:
                body = response.text[:500]
                log.error(
                    "kufar_search_http_error",
                    status=response.status_code,
                    body=body,
                    params=params,
                )
                response.raise_for_status()

            payload: dict[str, Any] = response.json()
            ads = payload.get("ads") or []
            total = payload.get("total")
            log.info(
                "kufar_search_page",
                page=page + 1,
                ads_on_page=len(ads),
                total=total,
                since=str(since) if since else None,
            )
            if not ads:
                break

            stop = False
            page_too_old = 0
            for raw in ads:
                listing = parse_listing(raw)
                if since and listing.list_time <= since:
                    page_too_old += 1
                    stop = True
                    break
                listings.append(listing)

            if page_too_old:
                log.info("kufar_search_stop_old", page=page + 1, page_too_old=page_too_old)
            if stop:
                break

            pagination = payload.get("pagination") or {}
            pages = pagination.get("pages") or []
            next_cursor = None
            for item in pages:
                if item.get("label") == "next":
                    next_cursor = item.get("token")
                    break
            if not next_cursor:
                break
            cursor = next_cursor

        log.info("kufar_search_done", fetched=len(listings), query=query)
        return listings

    async def collect_since_watermark(
        self,
        api_query: dict[str, str] | str,
        *,
        watermark_ad_id: int | None = None,
        since: datetime | None = None,
        max_pages: int | None = None,
    ) -> tuple[list[AdListing], bool]:
        """Собирает объявления сверху выдачи до якоря (не включая якорь)."""
        if isinstance(api_query, str):
            query = json.loads(api_query)
        else:
            query = dict(api_query)

        page_limit = max_pages or (
            settings.poll_watermark_max_pages
            if watermark_ad_id is not None
            else settings.poll_max_pages
        )

        listings: list[AdListing] = []
        cursor: str | None = None
        anchor_found = watermark_ad_id is None

        for page in range(page_limit):
            params = api_query_to_params(query, cursor=cursor)
            response = await self.session.get(SEARCH_API, params=params, timeout=30)
            if response.status_code != 200:
                body = response.text[:500]
                log.error(
                    "kufar_search_http_error",
                    status=response.status_code,
                    body=body,
                    params=params,
                )
                response.raise_for_status()

            payload: dict[str, Any] = response.json()
            ads = payload.get("ads") or []
            log.info(
                "kufar_watermark_page",
                page=page + 1,
                ads_on_page=len(ads),
                watermark=watermark_ad_id,
                anchor_found=anchor_found,
            )
            if not ads:
                break

            stop = False
            for raw in ads:
                listing = parse_listing(raw)
                if watermark_ad_id is not None and listing.ad_id == watermark_ad_id:
                    anchor_found = True
                    stop = True
                    break
                if since and listing.list_time <= since:
                    if watermark_ad_id is None or not anchor_found:
                        stop = True
                        break
                listings.append(listing)

            if stop:
                break

            pagination = payload.get("pagination") or {}
            pages = pagination.get("pages") or []
            next_cursor = None
            for item in pages:
                if item.get("label") == "next":
                    next_cursor = item.get("token")
                    break
            if not next_cursor:
                break
            cursor = next_cursor

        deduped: list[AdListing] = []
        seen_ids: set[int] = set()
        for listing in listings:
            if listing.ad_id in seen_ids:
                continue
            seen_ids.add(listing.ad_id)
            deduped.append(listing)

        log.info(
            "kufar_watermark_done",
            fetched=len(deduped),
            raw_fetched=len(listings),
            watermark=watermark_ad_id,
            anchor_found=anchor_found,
        )
        return deduped, anchor_found

    async def fetch_top_ad_id(self, api_query: dict[str, str] | str) -> int | None:
        listings = await self.search_listings(api_query, max_pages=1)
        return listings[0].ad_id if listings else None

    async def fetch_listing(self, ad_id: int) -> AdListing | None:
        url = f"https://www.kufar.by/item/{ad_id}"
        try:
            html = await self.fetch_text(url)
        except Exception as exc:
            log.warning("listing_fetch_failed", ad_id=ad_id, error=str(exc))
            return None
        if "404" in html[:300] and "Not Found" in html:
            log.info("listing_not_found", ad_id=ad_id)
            return None
        listing = parse_ad_from_item_page(html)
        if listing:
            log.debug("listing_fetched", ad_id=ad_id, title=listing.subject, has_body=bool(listing.body))
        return listing

    async def enrich_with_description(self, listing: AdListing) -> AdListing:
        need_body = settings.kufar_fetch_description and not listing.body
        need_photos = len(listing.photo_urls) <= 1
        if not need_body and not need_photos:
            return listing
        full = await self.fetch_listing(listing.ad_id)
        if full is None:
            return listing
        result = listing
        if need_body and full.body:
            result = result.with_body(full.body)
        if need_photos and len(full.photo_urls) > len(result.photo_urls):
            result = result.with_photos(full.photo_urls)
        return result
