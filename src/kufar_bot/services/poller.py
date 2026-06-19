from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from sqlalchemy.ext.asyncio import AsyncSession

from kufar_bot.config import settings
from kufar_bot.db import repository as repo
from kufar_bot.db.models import SearchUrl, User
from kufar_bot.kufar.client import KufarClient
from kufar_bot.kufar.filters import is_blocked_by_phrases
from kufar_bot.kufar.models import AdListing
from kufar_bot.services.listing_digest import send_listings_digest
from kufar_bot.services.listing_send import send_listing
from kufar_bot.services.poll_cancel import poll_cancel
from kufar_bot.services.poll_stats import GroupPollStats, PollStats, UrlPollStats
from kufar_bot.services.telegram_retry import with_flood_retry

log = structlog.get_logger(__name__)


async def _process_search_url(
    session: AsyncSession,
    bot: Bot,
    client: KufarClient,
    user_id: int,
    group,
    search_url,
    phrases,
    *,
    fallback_since: datetime,
    send_limit: int,
    sent_count: int,
) -> tuple[UrlPollStats, int]:
    url_stats = UrlPollStats(url=search_url.url)
    fresh_url = await session.get(SearchUrl, search_url.id)
    if fresh_url is not None:
        search_url = fresh_url

    seen_cache = await repo.load_seen_ad_ids(
        session,
        user_id,
        search_url_id=search_url.id,
        group_id=group.id,
    )
    log.info(
        "poll_url_start",
        user_id=user_id,
        url_id=search_url.id,
        seen_in_db=len(seen_cache),
        watermark=search_url.watermark_ad_id,
        last_polled_at=search_url.last_polled_at,
    )

    watermark = search_url.watermark_ad_id
    # После «Сбросить опрос» watermark и last_polled_at = NULL — всегда окно 24 ч,
    # даже если в БД остались старые seen на уровне группы.
    first_run = watermark is None and search_url.last_polled_at is None
    since_cutoff: datetime | None = None
    if search_url.last_polled_at is not None:
        since_cutoff = search_url.last_polled_at
        if since_cutoff.tzinfo is None:
            since_cutoff = since_cutoff.replace(tzinfo=UTC)

    if watermark is not None:
        since = since_cutoff
        max_pages = settings.poll_watermark_max_pages
    elif first_run:
        since = datetime.now(UTC) - timedelta(hours=settings.poll_first_run_hours)
        max_pages = settings.poll_watermark_max_pages
        url_stats.first_run = True
    else:
        since = search_url.last_polled_at or fallback_since
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        max_pages = settings.poll_watermark_max_pages

    try:
        if poll_cancel.is_cancelled(user_id):
            return url_stats, sent_count

        raw_listings, anchor_found = await client.collect_since_watermark(
            search_url.api_query,
            watermark_ad_id=watermark,
            since=since,
            max_pages=max_pages,
        )
        url_stats.fetched = len(raw_listings)
        url_stats.watermark_found = anchor_found

        to_send: list[AdListing] = []
        batch_seen: set[int] = set()
        for listing in raw_listings:
            if listing.ad_id in seen_cache or listing.ad_id in batch_seen:
                url_stats.already_seen += 1
                continue
            batch_seen.add(listing.ad_id)
            if is_blocked_by_phrases(listing.searchable_text, phrases, group_id=group.id):
                url_stats.minus_filtered += 1
                await repo.mark_listing_seen(
                    session,
                    user_id,
                    listing.ad_id,
                    search_url_id=search_url.id,
                    group_id=group.id,
                    seen_cache=seen_cache,
                    commit=False,
                )
                continue
            to_send.append(listing)

        url_stats.new_found = len(to_send)

        if to_send and send_limit > 0 and sent_count >= send_limit:
            url_stats.skipped_limit = len(to_send)
            log.info("poll_send_limit_reached", user_id=user_id, limit=send_limit)
        elif to_send:
            if poll_cancel.is_cancelled(user_id):
                return url_stats, sent_count
            use_digest = len(to_send) > settings.poll_digest_threshold
            should_stop = lambda: poll_cancel.is_cancelled(user_id)
            if use_digest:
                marked_in_digest: list[int] = []

                async def mark_digest_chunk(ad_ids: list[int]) -> None:
                    await repo.mark_listings_seen_batch(
                        session,
                        user_id,
                        ad_ids,
                        search_url_id=search_url.id,
                        group_id=group.id,
                        seen_cache=seen_cache,
                    )
                    marked_in_digest.extend(ad_ids)

                completed, cancelled = await send_listings_digest(
                    bot,
                    user_id,
                    to_send,
                    group_name=group.name,
                    search_url=search_url.url,
                    should_stop=should_stop,
                    on_chunk_sent=mark_digest_chunk,
                )
                url_stats.sent = len(marked_in_digest)
                url_stats.digest_sent = completed and url_stats.sent > 0
                sent_count += url_stats.sent
                if cancelled:
                    log.info(
                        "digest_stopped",
                        user_id=user_id,
                        url_id=search_url.id,
                        sent=url_stats.sent,
                        total=len(to_send),
                    )
            else:
                for listing in to_send:
                    if poll_cancel.is_cancelled(user_id):
                        break
                    if send_limit > 0 and sent_count >= send_limit:
                        url_stats.skipped_limit += 1
                        continue
                    try:
                        sent_ok = await send_listing(
                            bot, user_id, listing, group, client=client,
                            section_label=search_url.section_label or None,
                        )
                    except Exception:
                        log.exception(
                            "listing_send_failed",
                            user_id=user_id,
                            ad_id=listing.ad_id,
                            group_id=group.id,
                        )
                        continue
                    if not sent_ok:
                        continue
                    await repo.mark_listing_seen(
                        session,
                        user_id,
                        listing.ad_id,
                        search_url_id=search_url.id,
                        group_id=group.id,
                        seen_cache=seen_cache,
                        commit=False,
                    )
                    url_stats.sent += 1
                    sent_count += 1
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        if session.new:
            await session.commit()

        if poll_cancel.is_cancelled(user_id):
            log.info("poll_url_cancelled", user_id=user_id, url_id=search_url.id)
            return url_stats, sent_count

        # Не сдвигаем якорь, если новые объявления так и не ушли в Telegram.
        if url_stats.new_found > 0 and url_stats.sent == 0:
            log.warning(
                "poll_watermark_skipped_unsent",
                user_id=user_id,
                url_id=search_url.id,
                new_found=url_stats.new_found,
            )
            return url_stats, sent_count

        top_ad_id = await client.fetch_top_ad_id(search_url.api_query)
        await repo.update_search_url_watermark(
            session,
            search_url.id,
            watermark_ad_id=top_ad_id,
        )

        log.info(
            "poll_url_done",
            user_id=user_id,
            group_id=group.id,
            url_id=search_url.id,
            fetched=url_stats.fetched,
            sent=url_stats.sent,
            digest=url_stats.digest_sent,
            watermark=top_ad_id,
            anchor_found=url_stats.watermark_found,
        )
    except Exception as exc:
        await session.rollback()
        url_stats.error = str(exc)
        log.exception(
            "poll_url_failed",
            user_id=user_id,
            group_id=group.id,
            url=search_url.url,
        )

    return url_stats, sent_count


async def poll_user(
    session: AsyncSession,
    bot: Bot,
    user_id: int,
    *,
    manual: bool = False,
) -> PollStats:
    stats = PollStats(user_id=user_id, since_iso="")
    log.info("poll_start", user_id=user_id, manual=manual)

    try:
        user = await session.get(User, user_id)
        if user is None or not repo.user_has_access(user):
            stats.fatal_error = "Нет доступа"
            log.warning("poll_denied", user_id=user_id)
            return stats

        groups = await repo.get_user_groups(session, user_id)
        active_groups = [g for g in groups if g.is_active and g.urls]
        log.info(
            "poll_groups",
            user_id=user_id,
            total_groups=len(groups),
            active_groups=len(active_groups),
        )

        if not active_groups:
            stats.fatal_error = "Нет активных групп с ссылками"
            if manual:
                await bot.send_message(user_id, stats.fatal_error)
            return stats

        last_run = await repo.get_last_poll_run(session, user_id)
        fallback_since = (
            last_run.finished_at
            if last_run and last_run.finished_at
            else datetime.now(UTC) - timedelta(hours=24)
        )
        if fallback_since.tzinfo is None:
            fallback_since = fallback_since.replace(tzinfo=UTC)
        stats.since_iso = fallback_since.astimezone().strftime("%d.%m.%Y %H:%M")

        run = await repo.start_poll_run(session, user_id)
        sent_count = 0
        send_limit = settings.poll_max_send_per_run
        log.info("poll_run_started", user_id=user_id, run_id=run.id, since=stats.since_iso)

        async with KufarClient() as client:
            for group in active_groups:
                if poll_cancel.is_cancelled(user_id):
                    stats.cancelled = True
                    break
                if send_limit > 0 and sent_count >= send_limit:
                    break

                group_stats = GroupPollStats(group_id=group.id, group_name=group.name)
                phrases = await repo.get_negative_phrases(
                    session, user_id, group_id=group.id, include_global=True
                )
                log.info(
                    "poll_group",
                    user_id=user_id,
                    group_id=group.id,
                    group_name=group.name,
                    urls=len(group.urls),
                    minus_phrases=len(phrases),
                )

                for search_url in group.urls:
                    if poll_cancel.is_cancelled(user_id):
                        stats.cancelled = True
                        break
                    if send_limit > 0 and sent_count >= send_limit:
                        break

                    url_stats, sent_count = await _process_search_url(
                        session,
                        bot,
                        client,
                        user_id,
                        group,
                        search_url,
                        phrases,
                        fallback_since=fallback_since,
                        send_limit=send_limit,
                        sent_count=sent_count,
                    )
                    group_stats.urls.append(url_stats)
                    if poll_cancel.is_cancelled(user_id):
                        stats.cancelled = True
                        break

                if not poll_cancel.is_cancelled(user_id):
                    stats.groups.append(group_stats)
                elif group_stats.urls:
                    stats.groups.append(group_stats)
                if poll_cancel.is_cancelled(user_id):
                    break

            if not poll_cancel.is_cancelled(user_id):
                favorites = await repo.get_favorites(session, user_id, active_only=True)
                stats.favorites_checked = len(favorites)
                await check_favorites(session, bot, user_id, client)

        await repo.finish_poll_run(session, run.id)
        log.info(
            "poll_finish",
            user_id=user_id,
            run_id=run.id,
            sent=sent_count,
            errors=stats.errors,
        )

        if manual:
            try:
                await with_flood_retry(
                    "poll_summary",
                    lambda: bot.send_message(
                        user_id, stats.summary_text(), parse_mode="HTML"
                    ),
                )
            except TelegramRetryAfter:
                log.warning("poll_summary_flood_skipped", user_id=user_id)

    except Exception as exc:
        await session.rollback()
        stats.fatal_error = str(exc)
        log.exception("poll_fatal", user_id=user_id)
        if manual and not isinstance(exc, TelegramRetryAfter):
            try:
                await with_flood_retry(
                    "poll_error",
                    lambda: bot.send_message(
                        user_id,
                        f"Ошибка опроса: {exc}\nПодробности: data/kufar_bot.log",
                    ),
                )
            except Exception:
                log.warning("poll_error_notify_failed", user_id=user_id)

    return stats


async def check_favorites(
    session: AsyncSession,
    bot: Bot,
    user_id: int,
    client: KufarClient,
) -> None:
    favorites = await repo.get_favorites(session, user_id, active_only=True)
    now = datetime.now(UTC)
    log.info("favorites_check", user_id=user_id, count=len(favorites))

    for fav in favorites:
        listing = await client.fetch_listing(fav.ad_id)
        fav.last_checked_at = now

        if listing is None:
            fav.is_active = False
            await session.commit()
            log.info("favorite_inactive", user_id=user_id, ad_id=fav.ad_id)
            await bot.send_message(
                user_id,
                f"❌ Лот снят с публикации:\n<b>{fav.title}</b>\n{fav.url}",
                parse_mode="HTML",
            )
            continue

        current_price = listing.price_byn or listing.price_usd
        if current_price is not None and fav.last_price is not None and current_price < fav.last_price:
            old = fav.last_price / 100
            new = current_price / 100
            log.info(
                "favorite_price_drop",
                user_id=user_id,
                ad_id=fav.ad_id,
                old=old,
                new=new,
            )
            await bot.send_message(
                user_id,
                f"📉 Цена снизилась!\n<b>{listing.subject}</b>\n"
                f"{old:.2f} → {new:.2f}\n{listing.url}",
                parse_mode="HTML",
            )
            fav.last_price = current_price
            fav.title = listing.subject
        elif current_price is not None:
            fav.last_price = current_price
            fav.title = listing.subject

        await session.commit()
