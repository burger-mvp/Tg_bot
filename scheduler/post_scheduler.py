"""Публикация очереди в рабочие часы и однократные повторы через семь дней."""

import logging
from datetime import datetime, time, timedelta
from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from config import CHANNEL_ID, SCHEDULER_TIMEZONE
from database import (
    claim_next_queued_post,
    claim_post_for_duplicate,
    delete_duplicated_post,
    get_posts_waiting_for_duplicate,
    mark_duplicate_failed,
    mark_post_published,
    mark_publication_failed,
    recover_interrupted_duplicates,
    recover_interrupted_posts,
)
from utils.publishing import send_queued_post


logger = logging.getLogger(__name__)
WORKDAY_START = time(hour=9)
WORKDAY_END = time(hour=22)
SLOT_INTERVAL = timedelta(minutes=30)
DUPLICATE_RETRY_DELAY = timedelta(minutes=5)


def next_publication_slot(now: datetime | None = None) -> datetime:
    """Возвращает ближайший допустимый 30-минутный слот между 09:00 и 22:00."""
    current = now.astimezone(SCHEDULER_TIMEZONE) if now else datetime.now(SCHEDULER_TIMEZONE)
    day_start = current.replace(hour=WORKDAY_START.hour, minute=0, second=0, microsecond=0)
    day_end = current.replace(hour=WORKDAY_END.hour, minute=0, second=0, microsecond=0)

    if current < day_start:
        return day_start
    if current > day_end:
        return day_start + timedelta(days=1)

    candidate = current.replace(second=0, microsecond=0)
    if candidate.minute not in {0, 30} or current.second or current.microsecond:
        candidate = candidate.replace(minute=30 if candidate.minute < 30 else 0)
        if candidate.minute == 0 and current.minute >= 30:
            candidate += timedelta(hours=1)
    if candidate < current:
        candidate += SLOT_INTERVAL
    if candidate > day_end:
        return day_start + timedelta(days=1)
    return candidate


class PostScheduler:
    """Координирует PostgreSQL-очередь и задачи APScheduler."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._scheduler = AsyncIOScheduler(timezone=SCHEDULER_TIMEZONE)

    async def start(self) -> None:
        """Восстанавливает повторы после рестарта и запускает проверку слотов."""
        await recover_interrupted_posts(next_publication_slot())
        await recover_interrupted_duplicates()
        self._scheduler.add_job(
            self.publish_next_post,
            CronTrigger(hour="9-21", minute="0,30", timezone=SCHEDULER_TIMEZONE),
            id="publish_queue_half_hour_slots",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self._scheduler.add_job(
            self.publish_next_post,
            CronTrigger(hour="22", minute="0", timezone=SCHEDULER_TIMEZONE),
            id="publish_queue_last_slot",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        now = datetime.now(SCHEDULER_TIMEZONE)
        for post_id, duplicate_due_at in await get_posts_waiting_for_duplicate():
            # После долгого простоя APScheduler не запускает просроченный DateTrigger.
            # В этом случае запускаем повтор сразу после старта, не теряя публикацию.
            self.schedule_duplicate(post_id, max(duplicate_due_at, now))
        self._scheduler.start()

    def shutdown(self) -> None:
        """Останавливает планировщик без ожидания уже несуществующих задач."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def publish_next_post(self) -> None:
        """Отправляет только один пост в текущем слоте очереди."""
        now = datetime.now(SCHEDULER_TIMEZONE)
        current_time = now.time().replace(tzinfo=None)
        if current_time < WORKDAY_START or current_time > WORKDAY_END:
            return

        post = await claim_next_queued_post()
        if post is None:
            return
        try:
            await send_queued_post(self._bot, CHANNEL_ID, post)
        except TelegramAPIError as error:
            logger.exception("Не удалось опубликовать пост %s в канале: %s", post.id, error)
            await mark_publication_failed(post.id, str(error), next_publication_slot(now + SLOT_INTERVAL))
            return

        duplicate_due_at = await mark_post_published(post.id)
        if duplicate_due_at is not None:
            self.schedule_duplicate(post.id, duplicate_due_at)

    def schedule_duplicate(self, post_id: UUID, run_date: datetime) -> None:
        """Планирует точный однократный повтор публикации."""
        self._scheduler.add_job(
            self.duplicate_post,
            DateTrigger(run_date=run_date, timezone=SCHEDULER_TIMEZONE),
            args=[post_id],
            id=f"duplicate:{post_id}",
            replace_existing=True,
            misfire_grace_time=None,
        )

    async def duplicate_post(self, post_id: UUID) -> None:
        """Повторно публикует пост и удаляет его из базы только после успеха."""
        post = await claim_post_for_duplicate(post_id)
        if post is None:
            return
        try:
            await send_queued_post(self._bot, CHANNEL_ID, post)
        except TelegramAPIError as error:
            logger.exception("Не удалось повторно опубликовать пост %s: %s", post.id, error)
            await mark_duplicate_failed(post.id, str(error))
            self.schedule_duplicate(post.id, datetime.now(SCHEDULER_TIMEZONE) + DUPLICATE_RETRY_DELAY)
            return
        await delete_duplicated_post(post.id)
