"""Асинхронный слой доступа к PostgreSQL."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID

import asyncpg

from config import DATABASE_URL


_MIN_POOL_SIZE: Final = 1
_MAX_POOL_SIZE: Final = 10
_ERROR_MESSAGE_LIMIT: Final = 1_000
_pool: asyncpg.Pool | None = None


@dataclass(frozen=True, slots=True)
class QueuedPost:
    """Пост, который ожидает модерации, публикации или повторной отправки."""

    id: UUID
    author_telegram_id: int
    author_role: str
    language_code: str
    media_items: list[dict[str, str]]
    description: str
    post_kind: str
    price_data: dict[str, Any]
    post_text: str
    status: str
    approved_at: datetime | None
    scheduled_at: datetime
    published_at: datetime | None
    duplicate_due_at: datetime | None
    moderation_chat_id: int | None
    moderation_message_id: int | None


async def init_db() -> None:
    """Создает пул соединений с PostgreSQL перед запуском бота."""
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=_MIN_POOL_SIZE,
            max_size=_MAX_POOL_SIZE,
        )


async def close_db() -> None:
    """Корректно закрывает пул при завершении работы бота."""
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


def _get_pool() -> asyncpg.Pool:
    """Возвращает инициализированный пул или сообщает об ошибке конфигурации."""
    if _pool is None:
        raise RuntimeError("Пул PostgreSQL не инициализирован. Сначала вызовите init_db().")
    return _pool


def _decode_json(value: object, fallback: object) -> object:
    """Декодирует JSONB вне зависимости от настройки кодека asyncpg."""
    if value is None:
        return fallback
    if isinstance(value, str):
        return json.loads(value)
    return value


def _record_to_post(record: asyncpg.Record) -> QueuedPost:
    """Преобразует запись PostgreSQL в типизированную модель очереди."""
    media_value = _decode_json(record["media_file_ids"], [])
    prices_value = _decode_json(record["price_data"], {})
    media_items: list[dict[str, str]] = []
    if isinstance(media_value, list):
        for item in media_value:
            if isinstance(item, str):
                # Обратная совместимость с постами, сохраненными предыдущей версией.
                media_items.append({"type": "video", "file_id": item})
            elif isinstance(item, dict) and isinstance(item.get("file_id"), str):
                media_items.append(
                    {
                        "type": str(item.get("type", "video")),
                        "file_id": item["file_id"],
                    }
                )
    price_data = prices_value if isinstance(prices_value, dict) else {}

    return QueuedPost(
        id=record["id"],
        author_telegram_id=record["author_telegram_id"],
        author_role=record["author_role"],
        language_code=record["language_code"],
        media_items=media_items,
        description=record["description"],
        post_kind=record["post_kind"],
        price_data=price_data,
        post_text=record["post_text"],
        status=record["status"],
        approved_at=record["approved_at"],
        scheduled_at=record["scheduled_at"],
        published_at=record["published_at"],
        duplicate_due_at=record["duplicate_due_at"],
        moderation_chat_id=record["moderation_chat_id"],
        moderation_message_id=record["moderation_message_id"],
    )


async def upsert_user(telegram_id: int, role: str, language_code: str) -> None:
    """Создает пользователя или обновляет его актуальные роль и язык."""
    await _get_pool().execute(
        """
        INSERT INTO users (telegram_id, role, language_code)
        VALUES ($1, $2, $3)
        ON CONFLICT (telegram_id) DO UPDATE
        SET role = EXCLUDED.role,
            language_code = EXCLUDED.language_code
        """,
        telegram_id,
        role,
        language_code,
    )


async def get_user_language(telegram_id: int) -> str | None:
    """Возвращает выбранный язык или None, если язык еще не выбран."""
    return await _get_pool().fetchval(
        "SELECT language_code FROM users WHERE telegram_id = $1",
        telegram_id,
    )


async def get_user_phone_number(telegram_id: int) -> str | None:
    """Возвращает сохраненный номер телефона или None, если его еще нет."""
    return await _get_pool().fetchval(
        "SELECT phone_number FROM users WHERE telegram_id = $1",
        telegram_id,
    )


async def update_user_role(telegram_id: int, role: str) -> None:
    """Синхронизирует сохраненную роль с актуальными настройками окружения."""
    await _get_pool().execute(
        "UPDATE users SET role = $2 WHERE telegram_id = $1",
        telegram_id,
        role,
    )


async def save_phone_number_and_mark_registered(
    telegram_id: int,
    phone_number: str,
    role: str,
) -> bool:
    """Сохраняет контакт и возвращает True только для первой полной регистрации."""
    pool = _get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                UPDATE users
                SET phone_number = $2,
                    role = $3
                WHERE telegram_id = $1
                """,
                telegram_id,
                phone_number,
                role,
            )
            is_new_registration = await connection.fetchval(
                """
                UPDATE users
                SET registered_at = NOW()
                WHERE telegram_id = $1
                  AND registered_at IS NULL
                RETURNING TRUE
                """,
                telegram_id,
            )
    return bool(is_new_registration)


async def create_post(
    *,
    post_id: UUID,
    author_telegram_id: int,
    author_role: str,
    language_code: str,
    media_items: list[dict[str, str]],
    description: str,
    post_kind: str,
    price_data: dict[str, Any],
    post_text: str,
    status: str,
    scheduled_at: datetime,
) -> None:
    """Сохраняет собранный пост в очереди или в ожидании модерации."""
    await _get_pool().execute(
        """
        INSERT INTO post_queue (
            id, author_telegram_id, author_role, language_code, media_file_ids,
            description, post_kind, price_data, post_text, status, approved_at, scheduled_at
        )
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8::jsonb, $9, $10::varchar,
                CASE WHEN $10::varchar = 'queued' THEN NOW() ELSE NULL END,
                $11)
        """,
        post_id,
        author_telegram_id,
        author_role,
        language_code,
        json.dumps(media_items),
        description,
        post_kind,
        json.dumps(price_data),
        post_text,
        status,
        scheduled_at,
    )


async def set_moderation_message(post_id: UUID, chat_id: int, message_id: int) -> None:
    """Запоминает сообщение модерации, чтобы его можно было обновить после правки."""
    await _get_pool().execute(
        """
        UPDATE post_queue
        SET moderation_chat_id = $2,
            moderation_message_id = $3,
            updated_at = NOW()
        WHERE id = $1
          AND status = 'pending_moderation'
        """,
        post_id,
        chat_id,
        message_id,
    )


async def get_post(post_id: UUID) -> QueuedPost | None:
    """Возвращает пост по идентификатору."""
    record = await _get_pool().fetchrow(
        "SELECT * FROM post_queue WHERE id = $1",
        post_id,
    )
    return _record_to_post(record) if record is not None else None


async def approve_post(post_id: UUID, scheduled_at: datetime) -> QueuedPost | None:
    """Переводит ожидающий модерации пост в очередь публикаций."""
    record = await _get_pool().fetchrow(
        """
        UPDATE post_queue
        SET status = 'queued',
            approved_at = NOW(),
            scheduled_at = $2,
            updated_at = NOW(),
            last_error = NULL
        WHERE id = $1
          AND status = 'pending_moderation'
        RETURNING *
        """,
        post_id,
        scheduled_at,
    )
    return _record_to_post(record) if record is not None else None


async def update_pending_post_text(post_id: UUID, description: str, post_text: str) -> QueuedPost | None:
    """Сохраняет исправленное описание поста до его одобрения."""
    record = await _get_pool().fetchrow(
        """
        UPDATE post_queue
        SET description = $2,
            post_text = $3,
            updated_at = NOW()
        WHERE id = $1
          AND status = 'pending_moderation'
        RETURNING *
        """,
        post_id,
        description,
        post_text,
    )
    return _record_to_post(record) if record is not None else None


async def claim_next_queued_post() -> QueuedPost | None:
    """Атомарно резервирует один самый ранний пост для публикации."""
    record = await _get_pool().fetchrow(
        """
        WITH candidate AS (
            SELECT id
            FROM post_queue
            WHERE status = 'queued'
              AND scheduled_at <= NOW()
            ORDER BY approved_at NULLS LAST, created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE post_queue AS queue
        SET status = 'publishing',
            updated_at = NOW()
        FROM candidate
        WHERE queue.id = candidate.id
        RETURNING queue.*
        """
    )
    return _record_to_post(record) if record is not None else None


async def mark_post_published(post_id: UUID, duplicate_after: timedelta) -> datetime | None:
    """Фиксирует публикацию и возвращает момент однократного повтора."""
    return await _get_pool().fetchval(
        """
        UPDATE post_queue
        SET status = 'published',
            published_at = NOW(),
            duplicate_due_at = NOW() + $2::interval,
            updated_at = NOW(),
            last_error = NULL
        WHERE id = $1
          AND status = 'publishing'
        RETURNING duplicate_due_at
        """,
        post_id,
        duplicate_after,
    )


async def mark_publication_failed(
    post_id: UUID,
    error_message: str,
    scheduled_at: datetime,
) -> None:
    """Возвращает неотправленный пост в очередь следующего временного слота."""
    await _get_pool().execute(
        """
        UPDATE post_queue
        SET status = 'queued',
            attempts = attempts + 1,
            last_error = $2,
            scheduled_at = $3,
            updated_at = NOW()
        WHERE id = $1
          AND status = 'publishing'
        """,
        post_id,
        error_message[:_ERROR_MESSAGE_LIMIT],
        scheduled_at,
    )


async def get_posts_waiting_for_duplicate() -> list[tuple[UUID, datetime]]:
    """Возвращает опубликованные посты, чьи повторы еще должны быть запланированы."""
    rows = await _get_pool().fetch(
        """
        SELECT id, duplicate_due_at
        FROM post_queue
        WHERE status = 'published'
          AND duplicate_due_at IS NOT NULL
        """
    )
    return [(row["id"], row["duplicate_due_at"]) for row in rows]


async def recover_interrupted_posts(scheduled_at: datetime) -> None:
    """Возвращает в очередь посты, прерванные перезапуском до отметки об успехе."""
    await _get_pool().execute(
        """
        UPDATE post_queue
        SET status = 'queued',
            scheduled_at = $1,
            updated_at = NOW(),
            last_error = COALESCE(last_error, 'Публикация была прервана перезапуском сервиса.')
        WHERE status = 'publishing'
        """,
        scheduled_at,
    )


async def claim_post_for_duplicate(post_id: UUID) -> QueuedPost | None:
    """Атомарно резервирует пост для единственной повторной публикации."""
    record = await _get_pool().fetchrow(
        """
        UPDATE post_queue
        SET status = 'duplicate_publishing',
            updated_at = NOW()
        WHERE id = $1
          AND status = 'published'
          AND duplicate_due_at <= NOW()
        RETURNING *
        """,
        post_id,
    )
    return _record_to_post(record) if record is not None else None


async def recover_interrupted_duplicates() -> None:
    """Возвращает в ожидание повторы, прерванные перезапуском до отправки."""
    await _get_pool().execute(
        """
        UPDATE post_queue
        SET status = 'published',
            updated_at = NOW(),
            last_error = COALESCE(last_error, 'Повтор публикации был прерван перезапуском сервиса.')
        WHERE status = 'duplicate_publishing'
        """
    )


async def delete_duplicated_post(post_id: UUID) -> None:
    """Удаляет пост после успешной повторной публикации через семь дней."""
    await _get_pool().execute(
        "DELETE FROM post_queue WHERE id = $1 AND status = 'duplicate_publishing'",
        post_id,
    )


async def mark_duplicate_failed(post_id: UUID, error_message: str) -> None:
    """Оставляет пост для повторной попытки дублирования после ошибки Telegram."""
    await _get_pool().execute(
        """
        UPDATE post_queue
        SET status = 'published',
            attempts = attempts + 1,
            last_error = $2,
            updated_at = NOW()
        WHERE id = $1
          AND status = 'duplicate_publishing'
        """,
        post_id,
        error_message[:_ERROR_MESSAGE_LIMIT],
    )
