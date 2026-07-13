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


async def add_user(telegram_id: int, phone_number: str, role: str) -> None:
    """Добавляет пользователя; повторная регистрация не перезаписывает данные."""
    pool = _get_pool()
    await pool.execute(
        """
        INSERT INTO users (telegram_id, phone_number, role)
        VALUES ($1, $2, $3)
        ON CONFLICT (telegram_id) DO NOTHING
        """,
        telegram_id,
        phone_number,
        role,
    )


async def get_user_role(telegram_id: int) -> str | None:
    """Возвращает сохраненную роль пользователя или None, если его нет в БД."""
    pool = _get_pool()
    return await pool.fetchval(
        "SELECT role FROM users WHERE telegram_id = $1",
        telegram_id,
    )
