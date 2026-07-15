"""Тексты интерфейса на поддерживаемых языках."""

from typing import Final
from loc_data import RU_TEXTS, EN_TEXTS


DEFAULT_LANGUAGE_CODE: Final = "ru"
SUPPORTED_LANGUAGE_CODES: Final = frozenset({"ru", "en"})

TEXTS: Final[dict[str, dict[str, str]]] = {
    "ru": RU_TEXTS,
    "en": EN_TEXTS,
}


def normalize_language_code(language_code: str | None) -> str:
    """Возвращает поддерживаемый код языка или язык по умолчанию."""
    return language_code if language_code in SUPPORTED_LANGUAGE_CODES else DEFAULT_LANGUAGE_CODE


def t(language_code: str | None, key: str, **kwargs: object) -> str:
    """Возвращает локализованную строку по ключу."""
    return TEXTS[normalize_language_code(language_code)][key].format(**kwargs)
