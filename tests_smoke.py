"""Локальные проверки чистой бизнес-логики без Telegram и PostgreSQL."""

import asyncio
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from scheduler.post_scheduler import next_publication_slot
from utils.pricing import (
    BODY_MARKUP,
    ENGINE_MARKUP,
    TELEGRAM_CAPTION_LIMIT,
    convert_aed_to_usd,
    format_post_caption,
    format_post_text,
    parse_aed_price,
)
from utils.publishing import send_post_content


class FakeBot:
    """Минимальная имитация Telegram Bot для проверки отправки медиа."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def send_video(
        self,
        chat_id: int,
        video: str,
        caption: str | None = None,
        reply_markup: object | None = None,
    ) -> tuple[str, int, str, str | None]:
        del reply_markup
        result = ("video", chat_id, video, caption)
        self.calls.append(result)
        return result

    async def send_media_group(self, chat_id: int, media: list[object]) -> list[tuple[str, int, int]]:
        captions = [getattr(item, "caption", None) for item in media]
        result = ("group", chat_id, len(media), *captions)
        self.calls.append(result)
        return [result]

    async def send_document(
        self,
        chat_id: int,
        document: str,
        caption: str | None = None,
        reply_markup: object | None = None,
    ) -> tuple[str, int, str, str | None]:
        del reply_markup
        result = ("document", chat_id, document, caption)
        self.calls.append(result)
        return result


async def test_video_chunks() -> None:
    """Текст становится подписью первого медиа, без отдельного сообщения."""
    bot = FakeBot()
    assert await send_post_content(bot, 1, [{"type": "video", "file_id": "one"}], "text") == [
        ("video", 1, "one", "text"),
    ]
    assert await send_post_content(
        bot,
        1,
        [{"type": "video", "file_id": str(index)} for index in range(11)],
        "text",
    ) == [
        ("group", 1, 10, "text", None, None, None, None, None, None, None, None, None),
        ("video", 1, "10", None),
    ]
    assert await send_post_content(bot, 1, [{"type": "document", "file_id": "movie"}], "text") == [
        ("document", 1, "movie", "text"),
    ]


def test_prices_text_and_slots() -> None:
    """Проверяет обе формулы, обязательную шапку/подвал и временные границы."""
    assert convert_aed_to_usd(Decimal("366"), ENGINE_MARKUP) == 110
    assert convert_aed_to_usd(Decimal("366"), BODY_MARKUP) == 115

    text = format_post_text(
        "Описание",
        "engine_with_transmission",
        {"engine": {"usd": 110}, "engine_with_transmission": {"usd": 220}},
    )
    assert text.startswith("🇦🇪 🇨🇳 🇷🇺 🇰🇿")
    assert "$110 USD" in text and "$220 USD" in text
    assert "@Kpp_Motors_Roman" in text

    assert parse_aed_price("15000") == Decimal("15000")
    for invalid_price in ("15000 ", "10к", "12500.50", "0"):
        try:
            parse_aed_price(invalid_price)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Цена {invalid_price!r} не была отклонена")

    caption = format_post_caption("😀" * 4_000, "engine_only", {"engine": {"usd": 110}})
    assert len(caption.encode("utf-16-le")) // 2 <= TELEGRAM_CAPTION_LIMIT
    assert "...\n\nЦена ДВС: $110 USD" in caption
    assert caption.endswith("https://www.youtube.com/@KppMotors")

    moscow = ZoneInfo("Europe/Moscow")
    assert next_publication_slot(datetime(2026, 7, 13, 8, 29, tzinfo=moscow)).isoformat().startswith(
        "2026-07-13T09:00:00"
    )
    assert next_publication_slot(datetime(2026, 7, 13, 21, 31, tzinfo=moscow)).isoformat().startswith(
        "2026-07-13T22:00:00"
    )
    assert next_publication_slot(datetime(2026, 7, 13, 22, 1, tzinfo=moscow)).isoformat().startswith(
        "2026-07-14T09:00:00"
    )


if __name__ == "__main__":
    test_prices_text_and_slots()
    asyncio.run(test_video_chunks())
    print("Smoke checks passed.")
