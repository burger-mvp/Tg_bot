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


def _parse_optional_ids(name: str) -> list[int]:
    """Преобразует необязательную переменную с Telegram ID через запятую."""
    raw_ids = os.getenv(name, "")
    try:
        return [int(item.strip()) for item in raw_ids.split(",") if item.strip()]
    except ValueError as error:
        raise RuntimeError(f"{name} должен содержать Telegram ID через запятую.") from error


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


def _parse_positive_int(name: str, default: int) -> int:
    """Читает положительное целое значение окружения."""
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} должен быть целым числом.") from error
    if value <= 0:
        raise RuntimeError(f"{name} должен быть больше нуля.")
    return value


TOKEN = _required_value("TOKEN")
DATABASE_URL = _required_value("DATABASE_URL")

try:
    CHANNEL_ID = int(_required_value("CHANNEL_ID"))
except ValueError as error:
    raise RuntimeError("CHANNEL_ID должен быть целым числом.") from error

try:
    TEST_CHANNEL_ID = int(os.getenv("TEST_CHANNEL_ID") or os.getenv("TEST_CHAT") or str(CHANNEL_ID))
except ValueError as error:
    raise RuntimeError("TEST_CHANNEL_ID или TEST_CHAT должен быть целым числом.") from error

SUPER_ADMIN_IDS = _parse_admin_ids(_required_value("SUPER_ADMIN_IDS"))
ADMIN_IDS = _parse_admin_ids(_required_value("ADMIN_IDS"))
KM_LOGISTICS_IDS = _parse_optional_ids("KM_LOGISTICS_IDS")
SALES_MANAGER_IDS = _parse_optional_ids("SALES_MANAGER_IDS")
TEST_MODE = _parse_bool("TEST_MODE")
TELEGRAM_API_SERVER_URL = os.getenv("TELEGRAM_API_SERVER_URL", "").strip().rstrip("/") or None
WEB_PUBLIC_URL = os.getenv("WEB_PUBLIC_URL", "").strip().rstrip("/") or None
WEB_ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD", "").strip() or None
WEB_SYNC_API_KEY = os.getenv("WEB_SYNC_API_KEY", "").strip() or None
WEB_LISTING_RETENTION_DAYS = _parse_positive_int("WEB_LISTING_RETENTION_DAYS", 30)

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "").strip() or None
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip() or None
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip() or None
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "").strip() or None
S3_REGION = os.getenv("S3_REGION", "auto").strip() or "auto"

WEB_INTEGRATION_ENABLED = all(
    (S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME)
)
WEB_REMOTE_SYNC_ENABLED = bool(WEB_PUBLIC_URL and WEB_SYNC_API_KEY)

# Время работы очереди определяется в локальном часовом поясе бизнеса.
# По умолчанию публикации идут с 09:00 до 22:00 по московскому времени.
SCHEDULER_TIMEZONE_NAME = os.getenv("SCHEDULER_TIMEZONE", "Europe/Moscow")
try:
    SCHEDULER_TIMEZONE = ZoneInfo(SCHEDULER_TIMEZONE_NAME)
except ZoneInfoNotFoundError as error:
    raise RuntimeError(
        "SCHEDULER_TIMEZONE должен быть корректным именем часового пояса, например Europe/Moscow."
    ) from error
