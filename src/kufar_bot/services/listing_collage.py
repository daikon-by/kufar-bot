from __future__ import annotations

import asyncio
import math
from io import BytesIO

import structlog
from curl_cffi.requests import AsyncSession
from PIL import Image, ImageOps

from kufar_bot.config import settings

log = structlog.get_logger(__name__)

COLLAGE_MAX_WIDTH = 1200
COLLAGE_MAX_PHOTOS = 10
COLLAGE_GAP = 4
COLLAGE_BG = (240, 240, 240)
JPEG_QUALITY = 85


def _grid_size(count: int) -> tuple[int, int]:
    if count <= 1:
        return 1, 1
    if count == 2:
        return 2, 1
    if count == 3:
        return 2, 2
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    return cols, rows


def build_collage_from_images(images: list[Image.Image]) -> bytes:
    if not images:
        raise ValueError("collage requires at least one image")

    count = len(images)
    cols, rows = _grid_size(count)
    gap = COLLAGE_GAP if count > 1 else 0
    canvas_width = COLLAGE_MAX_WIDTH
    cell_width = (canvas_width - gap * (cols - 1)) // cols
    cell_height = cell_width
    canvas_height = rows * cell_height + gap * (rows - 1)

    canvas = Image.new("RGB", (canvas_width, canvas_height), COLLAGE_BG)
    for idx, image in enumerate(images):
        row, col = divmod(idx, cols)
        x = col * (cell_width + gap)
        y = row * (cell_height + gap)
        fitted = ImageOps.fit(
            image.convert("RGB"),
            (cell_width, cell_height),
            method=Image.Resampling.LANCZOS,
        )
        canvas.paste(fitted, (x, y))

    buffer = BytesIO()
    canvas.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


async def _download_image(session: AsyncSession, url: str) -> Image.Image | None:
    try:
        response = await session.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as exc:
        log.warning("collage_download_failed", url=url, error=str(exc))
        return None


async def fetch_collage_bytes(urls: list[str]) -> bytes | None:
    selected = urls[:COLLAGE_MAX_PHOTOS]
    if len(selected) < 2:
        return None

    async with AsyncSession(impersonate=settings.kufar_impersonate) as session:
        results = await asyncio.gather(*(_download_image(session, url) for url in selected))

    images = [img for img in results if img is not None]
    if len(images) < 2:
        log.warning("collage_not_enough_images", requested=len(selected), loaded=len(images))
        return None

    try:
        return build_collage_from_images(images)
    except Exception:
        log.exception("collage_build_failed", photos=len(images))
        return None
