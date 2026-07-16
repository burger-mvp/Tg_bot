"""Подготовка HTML-текста с премиум-эмодзи Telegram."""

import re
from html import escape
from typing import Final

from aiogram.types import MessageEntity


PREMIUM_EMOJI_IDS: Final[dict[str, str]] = {
    "❗️": "5274099962655816924",
    "⚠️": "5420323339723881652",
    "✏️": "5395444784611480792",
    "🇨🇳": "5447548939844725331",
    "🇷🇺": "5398017006165305287",
    "🇦🇪": "5445069334965657809",
    "🇰🇿": "5228885231318088701",
}

TG_EMOJI_TAG_RE: Final = re.compile(r"</?tg-emoji\b[^>]*>")
TG_EMOJI_FULL_TAG_RE: Final = re.compile(
    r'<tg-emoji\s+emoji-id="(?P<emoji_id>\d+)">(?P<emoji>.*?)</tg-emoji>',
)


def _telegram_utf16_length(text: str) -> int:
    """Возвращает длину текста в UTF-16 code units, как ожидает Telegram Bot API."""
    return len(text.encode("utf-16-le")) // 2


def premium_emoji_html(text: str) -> str:
    """Экранирует HTML и заменяет обычные эмодзи на Telegram premium emoji tags."""
    html_text = escape(text, quote=False)
    for emoji, emoji_id in PREMIUM_EMOJI_IDS.items():
        html_text = html_text.replace(emoji, f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>')
    return html_text


def strip_tg_emoji_tags(text: str) -> str:
    """Удаляет HTML-теги premium emoji, оставляя обычные эмодзи внутри."""
    return TG_EMOJI_TAG_RE.sub("", text)


def tg_emoji_html_to_entities(text: str) -> tuple[str, list[MessageEntity]]:
    """Преобразует <tg-emoji> HTML в plain text и custom_emoji entities."""
    plain_parts: list[str] = []
    entities: list[MessageEntity] = []
    source_position = 0
    telegram_offset = 0

    for match in TG_EMOJI_FULL_TAG_RE.finditer(text):
        prefix = text[source_position:match.start()]
        emoji = match.group("emoji")
        emoji_id = match.group("emoji_id")

        plain_parts.append(prefix)
        telegram_offset += _telegram_utf16_length(prefix)
        plain_parts.append(emoji)
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=telegram_offset,
                length=_telegram_utf16_length(emoji),
                custom_emoji_id=emoji_id,
            ),
        )
        telegram_offset += _telegram_utf16_length(emoji)
        source_position = match.end()

    plain_parts.append(text[source_position:])
    return "".join(plain_parts), entities
