from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog
from aiogram.exceptions import TelegramRetryAfter

log = structlog.get_logger(__name__)

T = TypeVar("T")
ShouldStop = Callable[[], bool] | None


async def interruptible_sleep(seconds: float, should_stop: ShouldStop = None) -> bool:
    """Sleep in small steps. Returns False if should_stop became True."""
    if seconds <= 0:
        return True
    step = 0.25
    elapsed = 0.0
    while elapsed < seconds:
        if should_stop and should_stop():
            return False
        wait = min(step, seconds - elapsed)
        await asyncio.sleep(wait)
        elapsed += wait
    return not (should_stop and should_stop())


async def with_flood_retry(
    action: str,
    call: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 30,
    should_stop: ShouldStop = None,
) -> T:
    """Wait and retry when Telegram returns flood control (429)."""
    for attempt in range(max_attempts):
        if should_stop and should_stop():
            raise asyncio.CancelledError(f"stopped during {action}")
        try:
            return await call()
        except TelegramRetryAfter as exc:
            wait = float(exc.retry_after) + 1.0
            log.warning(
                "telegram_flood_wait",
                action=action,
                wait_sec=wait,
                attempt=attempt + 1,
            )
            if not await interruptible_sleep(wait, should_stop):
                raise asyncio.CancelledError(f"stopped during flood wait for {action}")
    raise RuntimeError(f"Telegram flood limit: {action} failed after {max_attempts} attempts")


async def pause_between_sends(should_stop: ShouldStop = None) -> bool:
    from kufar_bot.config import settings

    if settings.telegram_send_delay_sec <= 0:
        return True
    return await interruptible_sleep(settings.telegram_send_delay_sec, should_stop)
