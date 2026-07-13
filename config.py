"""Загрузка и проверка настроек из переменных окружения."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


# При локальном запуске значения берутся из .env рядом с этим файлом.
# На Railway переменные окружения передаются платформой напрямую.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _required_value(name: str) -> str:
    """Возвращает обязательную переменную окружения или понятную ошибку."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Не задана обязательная переменная окружения: {name}")
    return value


def _parse_admin_ids(raw_ids: str) -> list[int]:
    """Преобразует строку ID через запятую в список целых чисел."""
    try:
        return [int(admin_id.strip()) for admin_id in raw_ids.split(",") if admin_id.strip()]
    except ValueError as error:
        raise RuntimeError("ADMIN_IDS должен содержать Telegram ID через запятую.") from error


def _parse_bool(name: str, default: bool = False) -> bool:
    """Читает булево значение окружения и отклоняет неоднозначные настройки."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    value = raw_value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    raise RuntimeError(f"{name} должен быть True или False.")


TOKEN = _required_value("TOKEN")
DATABASE_URL = _required_value("DATABASE_URL")

try:
    SUPER_ADMIN_ID = int(_required_value("SUPER_ADMIN_ID"))
    CHANNEL_ID = int(_required_value("CHANNEL_ID"))
except ValueError as error:
    raise RuntimeError("SUPER_ADMIN_ID и CHANNEL_ID должны быть целыми числами.") from error

ADMIN_IDS = _parse_admin_ids(_required_value("ADMIN_IDS"))
TEST_MODE = _parse_bool("TEST_MODE")
TELEGRAM_API_SERVER_URL = os.getenv("TELEGRAM_API_SERVER_URL", "").strip().rstrip("/") or None

# Время работы очереди определяется в локальном часовом поясе бизнеса.
# По умолчанию публикации идут с 09:00 до 22:00 по московскому времени.
SCHEDULER_TIMEZONE_NAME = os.getenv("SCHEDULER_TIMEZONE", "Europe/Moscow")
try:
    SCHEDULER_TIMEZONE = ZoneInfo(SCHEDULER_TIMEZONE_NAME)
except ZoneInfoNotFoundError as error:
    raise RuntimeError(
        "SCHEDULER_TIMEZONE должен быть корректным именем часового пояса, например Europe/Moscow."
    ) from error
