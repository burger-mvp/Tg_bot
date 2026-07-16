"""Подготовка HTML-текста с премиум-эмодзи Telegram."""

import re
from html import escape
from typing import Final


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


def premium_emoji_html(text: str) -> str:
    """Экранирует HTML и заменяет обычные эмодзи на Telegram premium emoji tags."""
    html_text = escape(text, quote=False)
    for emoji, emoji_id in PREMIUM_EMOJI_IDS.items():
        html_text = html_text.replace(emoji, f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>')
    return html_text


def strip_tg_emoji_tags(text: str) -> str:
    """Удаляет HTML-теги premium emoji, оставляя обычные эмодзи внутри."""
    return TG_EMOJI_TAG_RE.sub("", text)
