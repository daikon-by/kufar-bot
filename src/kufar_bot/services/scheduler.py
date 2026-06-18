from __future__ import annotations

from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from kufar_bot.db.models import User
from kufar_bot.db import repository as repo
from kufar_bot.db.session import async_session_factory
from kufar_bot.services.poll_cancel import poll_cancel
from kufar_bot.services.poller import poll_user

log = structlog.get_logger(__name__)

WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_scheduler: "PollScheduler | None" = None


def set_scheduler(scheduler: "PollScheduler") -> None:
    global _scheduler
    _scheduler = scheduler


def get_scheduler() -> "PollScheduler | None":
    return _scheduler


def parse_weekdays(value: str) -> str:
    days = [part.strip() for part in value.split(",") if part.strip() != ""]
    if not days:
        return "mon-sun"
    names = []
    for day in days:
        idx = int(day)
        if 0 <= idx <= 6:
            names.append(WEEKDAY_NAMES[idx])
    return ",".join(names) if names else "mon-sun"


class PollScheduler:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=ZoneInfo("Europe/Minsk"))

    async def start(self) -> None:
        self.scheduler.start()
        await self.reload_all()

    async def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)

    async def reload_all(self) -> None:
        self.scheduler.remove_all_jobs()
        async with async_session_factory() as session:
            users = await repo.get_authorized_users(session)
            for user in users:
                await self._register_user_jobs(session, user.telegram_id)

    async def reload_user(self, user_id: int) -> None:
        for job in list(self.scheduler.get_jobs()):
            if job.id.startswith(f"poll-{user_id}-"):
                job.remove()

        async with async_session_factory() as session:
            user = await session.get(User, user_id)
            if user and repo.user_has_access(user):
                await self._register_user_jobs(session, user_id)

    async def _register_user_jobs(self, session: AsyncSession, user_id: int) -> None:
        schedule = await repo.get_schedule(session, user_id)
        if not schedule.is_enabled:
            return

        weekdays = parse_weekdays(schedule.weekdays)
        tz = ZoneInfo(schedule.timezone)
        times = [part.strip() for part in schedule.run_times.split(",") if part.strip()]

        for time_value in times:
            hour, minute = time_value.split(":", 1)
            job_id = f"poll-{user_id}-{hour.zfill(2)}{minute.zfill(2)}"
            self.scheduler.add_job(
                self._run_poll,
                trigger=CronTrigger(
                    day_of_week=weekdays,
                    hour=int(hour),
                    minute=int(minute),
                    timezone=tz,
                ),
                id=job_id,
                replace_existing=True,
                kwargs={"user_id": user_id},
            )
            log.info("schedule_registered", user_id=user_id, job_id=job_id, weekdays=weekdays, time=time_value)

    async def _run_poll(self, user_id: int) -> None:
        if poll_cancel.is_active(user_id):
            log.warning("scheduled_poll_skipped_busy", user_id=user_id)
            return
        poll_cancel.start(user_id)
        try:
            async with async_session_factory() as session:
                await poll_user(session, self.bot, user_id)
        except Exception:
            log.exception("scheduled_poll_failed", user_id=user_id)
        finally:
            poll_cancel.clear(user_id)
