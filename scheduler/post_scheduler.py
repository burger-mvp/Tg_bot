"""Публикация очереди в рабочие часы и однократные повторы через семь дней."""

import logging
from datetime import datetime, time, timedelta
from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import CHANNEL_ID, SCHEDULER_TIMEZONE, TEST_CHANNEL_ID, TEST_MODE
from database import (
    accelerate_queue_for_test_mode,
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
from utils.web_sync import publish_post_to_web


logger = logging.getLogger(__name__)
WORKDAY_START = time(hour=8, minute=30)
WORKDAY_END = time(hour=21)
SLOT_INTERVAL = timedelta(minutes=30)
DUPLICATE_RETRY_DELAY = timedelta(minutes=5)
PENDING_DUPLICATES_SYNC_INTERVAL = timedelta(minutes=1)
TEST_QUEUE_INTERVAL = timedelta(minutes=1)
PRODUCTION_DUPLICATE_DELAY = timedelta(days=7)
TEST_DUPLICATE_DELAY = timedelta(minutes=3)


def publication_channel_id() -> int:
    """Возвращает канал публикации с учетом тестового режима."""
    return TEST_CHANNEL_ID if TEST_MODE else CHANNEL_ID


def queue_slot_interval() -> timedelta:
    """Возвращает интервал обработки очереди для текущего режима работы."""
    return TEST_QUEUE_INTERVAL if TEST_MODE else SLOT_INTERVAL


def duplicate_delay() -> timedelta:
    """Возвращает задержку единственного повтора публикации для текущего режима."""
    return TEST_DUPLICATE_DELAY if TEST_MODE else PRODUCTION_DUPLICATE_DELAY


def next_publication_slot(now: datetime | None = None) -> datetime:
    """Возвращает ближайший слот от текущего времени без учета уже занятой очереди."""
    current = now.astimezone(SCHEDULER_TIMEZONE) if now else datetime.now(SCHEDULER_TIMEZONE)
    if TEST_MODE:
        return current.replace(second=0, microsecond=0) + TEST_QUEUE_INTERVAL
    day_start = current.replace(hour=WORKDAY_START.hour, minute=WORKDAY_START.minute, second=0, microsecond=0)
    day_end = current.replace(hour=WORKDAY_END.hour, minute=WORKDAY_END.minute, second=0, microsecond=0)

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


def next_free_publication_slot(
    last_scheduled_at: datetime | None,
    now: datetime | None = None,
) -> datetime:
    """Возвращает следующий свободный слот после хвоста очереди."""
    if last_scheduled_at is None:
        return next_publication_slot(now)

    next_slot = last_scheduled_at.astimezone(SCHEDULER_TIMEZONE) + queue_slot_interval()
    day_start = next_slot.replace(hour=WORKDAY_START.hour, minute=WORKDAY_START.minute, second=0, microsecond=0)
    day_end = next_slot.replace(
        hour=WORKDAY_END.hour,
        minute=WORKDAY_END.minute,
        second=0,
        microsecond=0,
    )
    if next_slot < day_start or next_slot > day_end:
        return day_start + timedelta(days=1)
    return next_slot


class PostScheduler:
    """Координирует PostgreSQL-очередь и задачи APScheduler."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._scheduler = AsyncIOScheduler(timezone=SCHEDULER_TIMEZONE)

    async def start(self) -> None:
        """Восстанавливает повторы после рестарта и запускает проверку слотов."""
        await recover_interrupted_posts(next_publication_slot())
        await recover_interrupted_duplicates()
        if TEST_MODE:
            now = datetime.now(SCHEDULER_TIMEZONE)
            await accelerate_queue_for_test_mode(
                next_publication_slot(now),
                now + duplicate_delay(),
            )
        if TEST_MODE:
            self._scheduler.add_job(
                self.publish_next_post,
                IntervalTrigger(minutes=1, timezone=SCHEDULER_TIMEZONE),
                id="publish_queue_test_each_minute",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
        else:
            self._scheduler.add_job(
                self.publish_next_post,
                CronTrigger(hour="8-21", minute="0,30", timezone=SCHEDULER_TIMEZONE),
                id="publish_queue_half_hour_slots",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
        await self.sync_pending_duplicates()
        self._scheduler.add_job(
            self.sync_pending_duplicates,
            IntervalTrigger(minutes=1, timezone=SCHEDULER_TIMEZONE),
            id="sync_pending_duplicates",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self._scheduler.start()
        if TEST_MODE:
            await self.publish_next_post()

    async def sync_pending_duplicates(self) -> None:
        """Планирует все опубликованные посты, ожидающие единственного дубля."""
        now = datetime.now(SCHEDULER_TIMEZONE)
        for post_id, duplicate_due_at in await get_posts_waiting_for_duplicate():
            # После долгого простоя APScheduler не запускает просроченный DateTrigger.
            # В этом случае запускаем повтор сразу после старта, не теряя публикацию.
            self.schedule_duplicate(post_id, max(duplicate_due_at, now))

    def shutdown(self) -> None:
        """Останавливает планировщик без ожидания уже несуществующих задач."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def publish_next_post(self) -> None:
        """Отправляет только один пост в текущем слоте очереди."""
        now = datetime.now(SCHEDULER_TIMEZONE)
        current_time = now.time().replace(tzinfo=None)
        if not TEST_MODE and (current_time < WORKDAY_START or current_time > WORKDAY_END):
            return

        post = await claim_next_queued_post(ignore_schedule=TEST_MODE)
        if post is None:
            return
        channel_id = publication_channel_id()
        try:
            messages = await send_queued_post(self._bot, channel_id, post)
        except TelegramAPIError as error:
            logger.exception("Не удалось опубликовать пост %s в канале: %s", post.id, error)
            await mark_publication_failed(post.id, str(error), next_publication_slot(now + queue_slot_interval()))
            return

        try:
            await publish_post_to_web(self._bot, post)
        except Exception:
            logger.exception("Пост %s опубликован в Telegram, но не синхронизирован с сайтом", post.id)

        duplicate_due_at = await mark_post_published(
            post.id,
            duplicate_delay(),
            channel_id=channel_id,
            message_ids=[message.message_id for message in messages],
        )
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
        post = await claim_post_for_duplicate(post_id, ignore_schedule=TEST_MODE)
        if post is None:
            return
        try:
            await send_queued_post(self._bot, publication_channel_id(), post)
        except TelegramAPIError as error:
            logger.exception("Не удалось повторно опубликовать пост %s: %s", post.id, error)
            await mark_duplicate_failed(post.id, str(error))
            self.schedule_duplicate(post.id, datetime.now(SCHEDULER_TIMEZONE) + DUPLICATE_RETRY_DELAY)
            return
        await delete_duplicated_post(post.id)
