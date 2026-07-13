"""Правила назначения ролей по настройкам окружения."""

from config import ADMIN_IDS, SUPER_ADMIN_ID


def get_role(telegram_id: int) -> str:
    """Возвращает актуальную роль пользователя по его Telegram ID."""
    if telegram_id == SUPER_ADMIN_ID:
        return "super_admin"
    if telegram_id in ADMIN_IDS:
        return "admin"
    return "user"


def is_admin(telegram_id: int) -> bool:
    """Проверяет доступ к административным возможностям."""
    return get_role(telegram_id) in {"admin", "super_admin"}


def is_super_admin(telegram_id: int) -> bool:
    """Проверяет полномочия единственного супер-администратора."""
    return telegram_id == SUPER_ADMIN_ID


def notification_recipient_ids() -> set[int]:
    """Возвращает уникальный список получателей служебных уведомлений."""
    return {SUPER_ADMIN_ID, *ADMIN_IDS}
