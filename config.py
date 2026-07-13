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


TOKEN = _required_value("TOKEN")
DATABASE_URL = _required_value("DATABASE_URL")

try:
    SUPER_ADMIN_ID = int(_required_value("SUPER_ADMIN_ID"))
    CHANNEL_ID = int(_required_value("CHANNEL_ID"))
except ValueError as error:
    raise RuntimeError("SUPER_ADMIN_ID и CHANNEL_ID должны быть целыми числами.") from error

ADMIN_IDS = _parse_admin_ids(_required_value("ADMIN_IDS"))

# Время работы очереди определяется в локальном часовом поясе бизнеса.
# По умолчанию публикации идут с 09:00 до 22:00 по московскому времени.
SCHEDULER_TIMEZONE_NAME = os.getenv("SCHEDULER_TIMEZONE", "Europe/Moscow")
try:
    SCHEDULER_TIMEZONE = ZoneInfo(SCHEDULER_TIMEZONE_NAME)
except ZoneInfoNotFoundError as error:
    raise RuntimeError(
        "SCHEDULER_TIMEZONE должен быть корректным именем часового пояса, например Europe/Moscow."
    ) from error
