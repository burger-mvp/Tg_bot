"""Асинхронный доступ к PostgreSQL через пул asyncpg."""

from typing import Final

import asyncpg

from config import DATABASE_URL


_MIN_POOL_SIZE: Final = 1
_MAX_POOL_SIZE: Final = 10
_pool: asyncpg.Pool | None = None


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


async def user_exists(telegram_id: int) -> bool:
    """Проверяет, зарегистрирован ли пользователь с указанным Telegram ID."""
    pool = _get_pool()
    return await pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM users WHERE telegram_id = $1)",
        telegram_id,
    )


async def upsert_user(telegram_id: int, role: str, language_code: str) -> None:
    """Создает пользователя или обновляет его актуальные роль и язык."""
    pool = _get_pool()
    await pool.execute(
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


async def get_user_role(telegram_id: int) -> str | None:
    """Возвращает сохраненную роль пользователя или None, если его нет в БД."""
    pool = _get_pool()
    return await pool.fetchval(
        "SELECT role FROM users WHERE telegram_id = $1",
        telegram_id,
    )


async def get_user_language(telegram_id: int) -> str | None:
    """Возвращает выбранный язык или None, если язык еще не выбран."""
    pool = _get_pool()
    return await pool.fetchval(
        "SELECT language_code FROM users WHERE telegram_id = $1",
        telegram_id,
    )


async def get_user_phone_number(telegram_id: int) -> str | None:
    """Возвращает сохраненный номер телефона или None, если его еще нет."""
    pool = _get_pool()
    return await pool.fetchval(
        "SELECT phone_number FROM users WHERE telegram_id = $1",
        telegram_id,
    )


async def update_user_phone_number(telegram_id: int, phone_number: str) -> None:
    """Сохраняет номер телефона пользователя после выбора языка."""
    pool = _get_pool()
    await pool.execute(
        "UPDATE users SET phone_number = $2 WHERE telegram_id = $1",
        telegram_id,
        phone_number,
    )


async def update_user_role(telegram_id: int, role: str) -> None:
    """Синхронизирует сохраненную роль с актуальными настройками окружения."""
    pool = _get_pool()
    await pool.execute(
        "UPDATE users SET role = $2 WHERE telegram_id = $1",
        telegram_id,
        role,
    )


async def save_published_post(description: str, media_id: str | None) -> None:
    """Сохраняет факт успешной публикации в Telegram-канале."""
    pool = _get_pool()
    await pool.execute(
        """
        INSERT INTO posts (media_ids, description, status, published_at)
        VALUES ($1, $2, 'published', NOW())
        """,
        media_id,
        description,
    )
