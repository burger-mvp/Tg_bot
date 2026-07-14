"""Правила назначения ролей по настройкам окружения и БД."""

import asyncio

from config import ADMIN_IDS, SUPER_ADMIN_IDS


def get_role(telegram_id: int) -> str:
    """Возвращает актуальную роль пользователя по его Telegram ID из config."""
    # Эта функция используется для первичного определения роли из config
    # Для актуальной роли из БД используйте database.get_user_role()
    if telegram_id in SUPER_ADMIN_IDS:
        return "super_admin"
    if telegram_id in ADMIN_IDS:
        return "admin"
    return "user"


async def get_role_from_db_or_config(telegram_id: int) -> str:
    """Возвращает роль из БД или fallback на config."""
    from database import get_user_role
    
    # Супер-админы всегда определяются из config
    if telegram_id in SUPER_ADMIN_IDS:
        return "super_admin"
    
    # Пробуем получить роль из БД
    db_role = await get_user_role(telegram_id)
    if db_role in ("admin", "super_admin", "trusted_seller"):
        return db_role
    
    # Fallback на config для совместимости
    if telegram_id in ADMIN_IDS:
        return "admin"
    
    return "user"


def is_admin(telegram_id: int) -> bool:
    """Проверяет доступ к административным возможностям."""
    return get_role(telegram_id) in {"admin", "super_admin"}


async def is_admin_or_higher(telegram_id: int) -> bool:
    """Проверяет доступ к административным возможностям модерации (async версия с проверкой БД)."""
    role = await get_role_from_db_or_config(telegram_id)
    return role in {"admin", "super_admin"}


def is_super_admin(telegram_id: int) -> bool:
    """Проверяет полномочия супер-администратора."""
    return telegram_id in SUPER_ADMIN_IDS


def notification_recipient_ids() -> set[int]:
    """Возвращает список всех админов для уведомлений о регистрации."""
    return {*SUPER_ADMIN_IDS, *ADMIN_IDS}


def super_admin_ids() -> set[int]:
    """Возвращает список только супер-админов для уведомлений о постах."""
    return set(SUPER_ADMIN_IDS)
