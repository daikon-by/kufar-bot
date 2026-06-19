from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

TELEGRAM_MEDIA_GROUP_LIMIT = 10


@dataclass(slots=True)
class AdListing:
    ad_id: int
    subject: str
    url: str
    price_byn: int | None
    price_usd: int | None
    currency: str
    list_time: datetime
    body: str | None
    photo_url: str | None
    thumb_url: str | None = None
    photo_urls: list[str] = field(default_factory=list)
    area_label: str | None = None
    region_label: str | None = None

    @property
    def display_photo_url(self) -> str | None:
        if self.photo_urls:
            return self.photo_urls[0]
        if self.thumb_url:
            return self.thumb_url
        return self.photo_url

    @property
    def display_photo_urls(self) -> list[str]:
        if self.photo_urls:
            return self.photo_urls[:TELEGRAM_MEDIA_GROUP_LIMIT]
        if self.photo_url:
            return [self.photo_url]
        return []

    @property
    def display_price(self) -> str:
        if self.price_byn is not None and self.price_byn > 0:
            return f"{self.price_byn / 100:.2f} BYN"
        if self.price_usd is not None and self.price_usd > 0:
            return f"{self.price_usd / 100:.2f} USD"
        return "договорная"

    @property
    def location_label(self) -> str | None:
        area = (self.area_label or "").strip()
        region = (self.region_label or "").strip()
        if area and region and area not in region:
            return f"{area}, {region}"
        return area or region or None

    @property
    def searchable_text(self) -> str:
        parts = [self.subject or ""]
        if self.body:
            parts.append(self.body)
        return " ".join(parts).lower()

    def with_body(self, body: str | None) -> AdListing:
        if not body or body == self.body:
            return self
        return AdListing(
            ad_id=self.ad_id,
            subject=self.subject,
            url=self.url,
            price_byn=self.price_byn,
            price_usd=self.price_usd,
            currency=self.currency,
            list_time=self.list_time,
            body=body,
            photo_url=self.photo_url,
            thumb_url=self.thumb_url,
            photo_urls=list(self.photo_urls),
            area_label=self.area_label,
            region_label=self.region_label,
        )

    def with_photos(self, photo_urls: list[str]) -> AdListing:
        urls = photo_urls[:TELEGRAM_MEDIA_GROUP_LIMIT]
        first = urls[0] if urls else self.photo_url
        return AdListing(
            ad_id=self.ad_id,
            subject=self.subject,
            url=self.url,
            price_byn=self.price_byn,
            price_usd=self.price_usd,
            currency=self.currency,
            list_time=self.list_time,
            body=self.body,
            photo_url=first,
            thumb_url=self.thumb_url,
            photo_urls=urls,
            area_label=self.area_label,
            region_label=self.region_label,
        )
