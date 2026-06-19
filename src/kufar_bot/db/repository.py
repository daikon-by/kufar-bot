from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from kufar_bot.config import settings
from kufar_bot.db.models import (
    Favorite,
    NegativePhrase,
    PollRun,
    Schedule,
    SearchGroup,
    SearchUrl,
    SeenListing,
    User,
)


async def ensure_admins(session: AsyncSession) -> None:
    for admin_id in settings.admin_id_list:
        user = await session.get(User, admin_id)
        if user is None:
            session.add(
                User(
                    telegram_id=admin_id,
                    is_authorized=True,
                    is_admin=True,
                )
            )
        else:
            user.is_authorized = True
            user.is_admin = True
    await session.commit()


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None) -> User:
    user = await session.get(User, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.flush()
    elif username and user.username != username:
        user.username = username
    return user


def user_has_access(user: User) -> bool:
    if not user.is_authorized:
        return False
    if user.expires_at and user.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        return False
    return True


async def authorize_user(
    session: AsyncSession,
    telegram_id: int,
    *,
    days: int | None = None,
) -> User:
    user = await session.get(User, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id, is_authorized=True)
        session.add(user)
    else:
        user.is_authorized = True
    if days is not None:
        user.expires_at = datetime.now(UTC) + timedelta(days=days)
    else:
        user.expires_at = None
    await session.commit()
    await session.refresh(user)
    return user


async def revoke_user(session: AsyncSession, telegram_id: int) -> bool:
    user = await session.get(User, telegram_id)
    if user is None:
        return False
    if user.is_admin:
        return False
    user.is_authorized = False
    user.expires_at = None
    await session.commit()
    return True


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.scalars(select(User).order_by(User.created_at))
    return list(result)


async def get_user_groups(session: AsyncSession, user_id: int) -> list[SearchGroup]:
    result = await session.scalars(
        select(SearchGroup)
        .where(SearchGroup.user_id == user_id)
        .options(selectinload(SearchGroup.urls))
        .order_by(SearchGroup.name)
    )
    return list(result)


async def get_group_by_name(session: AsyncSession, user_id: int, name: str) -> SearchGroup | None:
    return await session.scalar(
        select(SearchGroup)
        .where(SearchGroup.user_id == user_id, SearchGroup.name == name)
        .options(selectinload(SearchGroup.urls))
        .limit(1)
    )


async def get_group(session: AsyncSession, group_id: int, user_id: int) -> SearchGroup | None:
    result = await session.scalar(
        select(SearchGroup)
        .where(SearchGroup.id == group_id, SearchGroup.user_id == user_id)
        .options(selectinload(SearchGroup.urls))
    )
    return result


async def create_group(
    session: AsyncSession,
    user_id: int,
    name: str,
    region_label: str,
    *,
    section_label: str = "",
) -> SearchGroup:
    group = SearchGroup(
        user_id=user_id,
        name=name,
        section_label=section_label,
        region_label=region_label,
    )
    session.add(group)
    await session.commit()
    loaded = await get_group(session, group.id, user_id)
    if loaded is None:
        raise RuntimeError(f"Failed to load created group id={group.id}")
    return loaded


async def add_group_url(
    session: AsyncSession,
    group_id: int,
    url: str,
    api_query: str,
    *,
    section_label: str = "",
) -> SearchUrl | None:
    existing = await session.scalar(
        select(SearchUrl).where(SearchUrl.group_id == group_id, SearchUrl.url == url)
    )
    if existing is not None:
        if section_label and not (existing.section_label or "").strip():
            existing.section_label = section_label.strip()
            await session.commit()
            await session.refresh(existing)
        return existing
    item = SearchUrl(
        group_id=group_id,
        url=url,
        api_query=api_query,
        section_label=section_label.strip(),
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def delete_group(session: AsyncSession, group_id: int, user_id: int) -> bool:
    group = await get_group(session, group_id, user_id)
    if group is None:
        return False
    await session.delete(group)
    await session.commit()
    return True


async def delete_group_url(session: AsyncSession, url_id: int, user_id: int) -> bool:
    item = await session.scalar(
        select(SearchUrl)
        .join(SearchGroup, SearchUrl.group_id == SearchGroup.id)
        .where(SearchUrl.id == url_id, SearchGroup.user_id == user_id)
    )
    if item is None:
        return False
    await session.delete(item)
    await session.commit()
    return True


async def get_negative_phrases(
    session: AsyncSession,
    user_id: int,
    *,
    group_id: int | None = None,
    include_global: bool = True,
) -> list[NegativePhrase]:
    stmt = select(NegativePhrase).where(NegativePhrase.user_id == user_id)
    if group_id is not None:
        if include_global:
            stmt = stmt.where(
                (NegativePhrase.group_id == group_id) | (NegativePhrase.group_id.is_(None))
            )
        else:
            stmt = stmt.where(NegativePhrase.group_id == group_id)
    else:
        stmt = stmt.where(NegativePhrase.group_id.is_(None))
    result = await session.scalars(stmt.order_by(NegativePhrase.phrase))
    return list(result)


async def add_negative_phrase(
    session: AsyncSession,
    user_id: int,
    phrase: str,
    *,
    group_id: int | None = None,
) -> NegativePhrase | None:
    normalized = phrase.strip().lower()
    if not normalized:
        return None
    stmt = select(NegativePhrase).where(
        NegativePhrase.user_id == user_id,
        NegativePhrase.phrase == normalized,
    )
    if group_id is None:
        stmt = stmt.where(NegativePhrase.group_id.is_(None))
    else:
        stmt = stmt.where(NegativePhrase.group_id == group_id)
    existing = await session.scalar(stmt)
    if existing:
        return existing
    item = NegativePhrase(user_id=user_id, phrase=normalized, group_id=group_id)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def delete_negative_phrase(session: AsyncSession, phrase_id: int, user_id: int) -> bool:
    item = await session.scalar(
        select(NegativePhrase).where(NegativePhrase.id == phrase_id, NegativePhrase.user_id == user_id)
    )
    if item is None:
        return False
    await session.delete(item)
    await session.commit()
    return True


async def get_negative_phrase(session: AsyncSession, phrase_id: int, user_id: int) -> NegativePhrase | None:
    return await session.scalar(
        select(NegativePhrase)
        .options(selectinload(NegativePhrase.group))
        .where(NegativePhrase.id == phrase_id, NegativePhrase.user_id == user_id)
    )


async def update_negative_phrase(
    session: AsyncSession,
    phrase_id: int,
    user_id: int,
    phrase: str,
) -> NegativePhrase | None:
    normalized = phrase.strip().lower()
    if not normalized:
        return None
    item = await get_negative_phrase(session, phrase_id, user_id)
    if item is None:
        return None
    item.phrase = normalized
    await session.commit()
    await session.refresh(item)
    return item


async def get_schedule(session: AsyncSession, user_id: int) -> Schedule:
    schedule = await session.get(Schedule, user_id)
    if schedule is None:
        schedule = Schedule(user_id=user_id)
        session.add(schedule)
        await session.commit()
        await session.refresh(schedule)
    return schedule


async def update_schedule(
    session: AsyncSession,
    user_id: int,
    *,
    weekdays: str | None = None,
    run_times: str | None = None,
    is_enabled: bool | None = None,
) -> Schedule:
    schedule = await get_schedule(session, user_id)
    if weekdays is not None:
        schedule.weekdays = weekdays
    if run_times is not None:
        schedule.run_times = run_times
    if is_enabled is not None:
        schedule.is_enabled = is_enabled
    await session.commit()
    await session.refresh(schedule)
    return schedule


async def get_last_poll_run(session: AsyncSession, user_id: int) -> PollRun | None:
    return await session.scalar(
        select(PollRun)
        .where(PollRun.user_id == user_id, PollRun.finished_at.is_not(None))
        .order_by(PollRun.finished_at.desc())
        .limit(1)
    )


async def start_poll_run(session: AsyncSession, user_id: int) -> PollRun:
    run = PollRun(user_id=user_id)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def finish_poll_run(session: AsyncSession, run_id: int) -> None:
    run = await session.get(PollRun, run_id)
    if run:
        run.finished_at = datetime.now(UTC)
        await session.commit()


async def is_listing_seen(
    session: AsyncSession,
    user_id: int,
    ad_id: int,
    *,
    search_url_id: int,
    group_id: int,
    seen_cache: set[int] | None = None,
) -> bool:
    if seen_cache is not None:
        return ad_id in seen_cache
    return await session.scalar(
        select(SeenListing.id).where(
            SeenListing.user_id == user_id,
            SeenListing.ad_id == ad_id,
            (
                (SeenListing.search_url_id == search_url_id)
                | (
                    SeenListing.search_url_id.is_(None)
                    & (SeenListing.group_id == group_id)
                )
            ),
        )
    ) is not None


async def load_seen_ad_ids(
    session: AsyncSession,
    user_id: int,
    *,
    search_url_id: int,
    group_id: int,
) -> set[int]:
    result = await session.scalars(
        select(SeenListing.ad_id).where(
            SeenListing.user_id == user_id,
            (SeenListing.search_url_id == search_url_id)
            | (
                SeenListing.search_url_id.is_(None)
                & (SeenListing.group_id == group_id)
            ),
        )
    )
    return set(result)


async def reset_search_url_poll_state(session: AsyncSession, search_url_id: int, user_id: int) -> bool:
    item = await session.scalar(
        select(SearchUrl)
        .join(SearchGroup, SearchUrl.group_id == SearchGroup.id)
        .where(SearchUrl.id == search_url_id, SearchGroup.user_id == user_id)
    )
    if item is None:
        return False
    item.watermark_ad_id = None
    item.last_polled_at = None
    await session.execute(
        delete(SeenListing).where(
            SeenListing.user_id == user_id,
            (
                (SeenListing.search_url_id == search_url_id)
                | (
                    SeenListing.search_url_id.is_(None)
                    & (SeenListing.group_id == item.group_id)
                )
            ),
        )
    )
    await session.commit()
    return True


async def reset_group_poll_state(session: AsyncSession, group_id: int, user_id: int) -> int:
    group = await get_group(session, group_id, user_id)
    if group is None:
        return 0
    count = 0
    for item in group.urls:
        item.watermark_ad_id = None
        item.last_polled_at = None
        count += 1
    url_ids = [item.id for item in group.urls]
    if url_ids:
        await session.execute(
            delete(SeenListing).where(
                SeenListing.user_id == user_id,
                (
                    SeenListing.search_url_id.in_(url_ids)
                    | (
                        SeenListing.search_url_id.is_(None)
                        & (SeenListing.group_id == group_id)
                    )
                ),
            )
        )
    await session.commit()
    return count


async def reset_section_poll_state(
    session: AsyncSession,
    group_id: int,
    user_id: int,
    section_label: str,
) -> int:
    group = await get_group(session, group_id, user_id)
    if group is None:
        return 0
    count = 0
    for item in group.urls:
        if (item.section_label or "").strip() != section_label.strip():
            continue
        item.watermark_ad_id = None
        item.last_polled_at = None
        await session.execute(
            delete(SeenListing).where(
                SeenListing.user_id == user_id,
                SeenListing.search_url_id == item.id,
            )
        )
        count += 1
    if count:
        await session.commit()
    return count


async def mark_listing_seen(
    session: AsyncSession,
    user_id: int,
    ad_id: int,
    *,
    search_url_id: int,
    group_id: int,
    seen_cache: set[int] | None = None,
    commit: bool = True,
) -> None:
    if seen_cache is not None and ad_id in seen_cache:
        return
    if seen_cache is None and await is_listing_seen(
        session, user_id, ad_id, search_url_id=search_url_id, group_id=group_id
    ):
        return
    session.add(
        SeenListing(
            user_id=user_id,
            ad_id=ad_id,
            group_id=group_id,
            search_url_id=search_url_id,
            notified_at=datetime.now(UTC),
        )
    )
    if seen_cache is not None:
        seen_cache.add(ad_id)
    if not commit:
        return
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        if seen_cache is not None:
            seen_cache.add(ad_id)


async def mark_listings_seen_batch(
    session: AsyncSession,
    user_id: int,
    ad_ids: list[int],
    *,
    search_url_id: int,
    group_id: int,
    seen_cache: set[int] | None = None,
) -> None:
    new_ids = [ad_id for ad_id in ad_ids if not seen_cache or ad_id not in seen_cache]
    if not new_ids:
        return
    now = datetime.now(UTC)
    chunk_size = 250
    for offset in range(0, len(new_ids), chunk_size):
        chunk = new_ids[offset : offset + chunk_size]
        for ad_id in chunk:
            session.add(
                SeenListing(
                    user_id=user_id,
                    ad_id=ad_id,
                    group_id=group_id,
                    search_url_id=search_url_id,
                    notified_at=now,
                )
            )
            if seen_cache is not None:
                seen_cache.add(ad_id)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            for ad_id in chunk:
                if seen_cache is not None:
                    seen_cache.add(ad_id)


async def update_search_url_watermark(
    session: AsyncSession,
    search_url_id: int,
    *,
    watermark_ad_id: int | None,
) -> None:
    item = await session.get(SearchUrl, search_url_id)
    if item is None:
        return
    item.watermark_ad_id = watermark_ad_id
    item.last_polled_at = datetime.now(UTC)
    await session.commit()


async def get_favorites(session: AsyncSession, user_id: int, *, active_only: bool = True) -> list[Favorite]:
    stmt = select(Favorite).where(Favorite.user_id == user_id)
    if active_only:
        stmt = stmt.where(Favorite.is_active.is_(True))
    result = await session.scalars(stmt.order_by(Favorite.added_at.desc()))
    return list(result)


async def add_favorite(
    session: AsyncSession,
    user_id: int,
    ad_id: int,
    title: str,
    url: str,
    photo_url: str | None,
    price: int | None,
    currency: str,
) -> Favorite:
    fav = await session.scalar(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.ad_id == ad_id)
    )
    if fav:
        fav.is_active = True
        fav.title = title
        fav.url = url
        fav.photo_url = photo_url
        fav.last_price = price
        fav.currency = currency
    else:
        fav = Favorite(
            user_id=user_id,
            ad_id=ad_id,
            title=title,
            url=url,
            photo_url=photo_url,
            last_price=price,
            currency=currency,
        )
        session.add(fav)
    await session.commit()
    await session.refresh(fav)
    return fav


async def deactivate_favorite(session: AsyncSession, favorite_id: int, user_id: int) -> Favorite | None:
    fav = await session.scalar(
        select(Favorite).where(Favorite.id == favorite_id, Favorite.user_id == user_id)
    )
    if fav is None:
        return None
    fav.is_active = False
    await session.commit()
    return fav


async def remove_favorite(session: AsyncSession, favorite_id: int, user_id: int) -> bool:
    fav = await session.scalar(
        select(Favorite).where(Favorite.id == favorite_id, Favorite.user_id == user_id)
    )
    if fav is None:
        return False
    await session.delete(fav)
    await session.commit()
    return True


async def get_authorized_users(session: AsyncSession) -> list[User]:
    result = await session.scalars(select(User).where(User.is_authorized.is_(True)))
    users = []
    now = datetime.now(UTC)
    for user in result:
        if user.expires_at and user.expires_at.replace(tzinfo=UTC) < now:
            continue
        users.append(user)
    return users


async def cleanup_old_seen(session: AsyncSession, days: int = 30) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    await session.execute(delete(SeenListing).where(SeenListing.first_seen_at < cutoff))
    await session.commit()
