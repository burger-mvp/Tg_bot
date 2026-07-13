"""Локальные проверки чистой бизнес-логики без Telegram и PostgreSQL."""

import asyncio
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from scheduler.post_scheduler import next_publication_slot
from utils.pricing import BODY_MARKUP, ENGINE_MARKUP, convert_aed_to_usd, format_post_text
from utils.publishing import send_post_content


class FakeBot:
    """Минимальная имитация Telegram Bot для проверки разбиения видео."""

    async def send_video(self, chat_id: int, video: str) -> tuple[str, int, str]:
        return ("video", chat_id, video)

    async def send_media_group(self, chat_id: int, media: list[object]) -> list[tuple[str, int, int]]:
        return [("group", chat_id, len(media))]

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: object | None = None,
    ) -> tuple[str, int, str]:
        del reply_markup
        return ("text", chat_id, text)


async def test_video_chunks() -> None:
    """Один файл отправляется как video, 11 файлов делятся на 10 + 1."""
    bot = FakeBot()
    assert await send_post_content(bot, 1, ["one"], "text") == [
        ("video", 1, "one"),
        ("text", 1, "text"),
    ]
    assert await send_post_content(bot, 1, [str(index) for index in range(11)], "text") == [
        ("group", 1, 10),
        ("video", 1, "10"),
        ("text", 1, "text"),
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
