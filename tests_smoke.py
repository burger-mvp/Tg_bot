"""Локальные проверки чистой бизнес-логики без Telegram и PostgreSQL."""

import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from keyboards import main_menu, media_step_keyboard, moderation_keyboard, start_keyboard
from locales import t
from scheduler.post_scheduler import next_publication_slot
from scheduler.post_scheduler import (
    TEST_DUPLICATE_DELAY,
    TEST_QUEUE_INTERVAL,
    duplicate_delay,
    next_free_publication_slot,
    publication_channel_id,
    queue_slot_interval,
)
from utils.pricing import (
    BODY_MARKUP,
    ENGINE_MARKUP,
    TELEGRAM_CAPTION_LIMIT,
    convert_aed_to_usd,
    format_post_caption,
    format_post_text,
    parse_aed_price,
)
from utils.premium_emoji import premium_emoji_html, strip_tg_emoji_tags
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
        parse_mode: str | None = None,
        reply_markup: object | None = None,
    ) -> tuple[str, int, str, str | None]:
        del parse_mode, reply_markup
        result = ("video", chat_id, video, caption)
        self.calls.append(result)
        return result

    async def send_photo(
        self,
        chat_id: int,
        photo: str,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: object | None = None,
    ) -> tuple[str, int, str, str | None]:
        del parse_mode, reply_markup
        result = ("photo", chat_id, photo, caption)
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
        parse_mode: str | None = None,
        reply_markup: object | None = None,
    ) -> tuple[str, int, str, str | None]:
        del parse_mode, reply_markup
        result = ("document", chat_id, document, caption)
        self.calls.append(result)
        return result

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: object | None = None,
    ) -> tuple[str, int, str, bool]:
        del parse_mode
        result = ("message", chat_id, text, reply_markup is not None)
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
    assert await send_post_content(
        bot,
        1,
        [{"type": "photo", "file_id": "photo"}, {"type": "video", "file_id": "video"}],
        "text",
    ) == [("group", 1, 2, "text", None)]
    assert await send_post_content(
        bot,
        1,
        [{"type": "photo", "file_id": "photo"}, {"type": "video", "file_id": "video"}],
        "text",
        text_reply_markup=object(),
    ) == [("group", 1, 2, "text", None), ("message", 1, "Управление постом:", True)]


def test_premium_emoji_html() -> None:
    """Премиум-эмодзи вставляются после безопасного HTML-экранирования."""
    html_text = premium_emoji_html('🇦🇪 <test> ⚠️ & ✏️')
    assert '<tg-emoji emoji-id="5445069334965657809">🇦🇪</tg-emoji>' in html_text
    assert '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji>' in html_text
    assert '<tg-emoji emoji-id="5395444784611480792">✏️</tg-emoji>' in html_text
    assert "&lt;test&gt;" in html_text
    assert " &amp; " in html_text
    assert strip_tg_emoji_tags(html_text) == "🇦🇪 &lt;test&gt; ⚠️ &amp; ✏️"


def test_main_menus_and_localization() -> None:
    """Проверяет состав клавиатур и ключевые локализованные тексты."""
    def button_texts(role: str) -> list[str]:
        return [button.text for row in main_menu(role, "ru").keyboard for button in row]

    assert button_texts("user") == ["Создать пост"]
    assert button_texts("admin") == ["Создать пост"]
    assert button_texts("super_admin") == [
        "Создать пост",
        "🌟 Назначить доверенного продавца",
        "👤 Назначить администратора",
        "📋 Просмотр очереди",
        "📊 Выгрузить users",
    ]
    assert media_step_keyboard("ru").keyboard[0][0].text == "✅ Медиа загружены"
    assert start_keyboard("ru").keyboard[0][0].text == "🚀 Начать"
    moderation_buttons = [row[0].text for row in moderation_keyboard("post-id", "ru").inline_keyboard]
    assert moderation_buttons == ["✅ Выложить", "✏️ Редактировать", "🚫 Отклонить", "❌ Заблокировать автора"]
    assert t("ru", "engine") == "Двигатель / ДВС"
    assert t("ru", "engine_with_transmission") == "Двигатель с КПП"
    assert t("ru", "enter_transmission_price") == "Введите цену двигателя с КПП в AED:"
    assert t("ru", "enter_engine_price") == "Введите цену двигателя в AED:"
    queue_status = t("ru", "queue_status", total=0, queued=0, published=0, waiting_duplicate=0)
    assert "Всего постов в очереди: 0" in queue_status
    assert t("en", "engine") == "Engine"
    assert t("en", "engine_with_transmission") == "Engine with Gearbox"
    assert t("en", "enter_transmission_price") == "Enter the engine with gearbox price in AED:"
    assert t("en", "enter_engine_price") == "Enter the engine price in AED:"
    assert "Бот помогает" in t("ru", "info_message")
    assert "The bot helps" in t("en", "info_message")
    assert "<tg-emoji" in t("ru", "info_message")
    assert "<tg-emoji" in t("en", "info_message")
    assert t("ru", "banned_user_message") == "Ваш аккаунт заблокирован администратором."
    assert t("en", "banned_user_message") == "Your account has been blocked by an administrator."


def test_prices_text_and_slots() -> None:
    """Проверяет обе формулы, обязательную шапку/подвал и временные границы."""
    assert convert_aed_to_usd(Decimal("366"), ENGINE_MARKUP) == 110
    assert convert_aed_to_usd(Decimal("366"), BODY_MARKUP) == 120
    assert convert_aed_to_usd(Decimal("1998"), ENGINE_MARKUP) == 610
    assert convert_aed_to_usd(Decimal("1628"), BODY_MARKUP) == 520

    text = format_post_text(
        "Описание",
        "engine_with_transmission",
        {"engine": {"usd": 110}, "engine_with_transmission": {"usd": 220}},
    )
    assert text.startswith("🇦🇪 🇨🇳 🇷🇺 🇰🇿")
    assert "$110 USD" in text and "$220 USD" in text
    assert "Цена только ДВС: $110 USD" in text
    assert "Цена ДВС с КПП: $220 USD" in text
    assert "Engine / ДВС" not in text
    assert "Gearbox / АКПП" not in text
    assert "АКПП" not in text
    assert "@Kpp_Motors_Roman" in text

    english_text = format_post_text(
        "Description",
        "engine_with_transmission",
        {"engine": {"usd": 110}, "engine_with_transmission": {"usd": 220}},
        language_code="en",
    )
    assert "Цена только ДВС: $110 USD" in english_text
    assert "Цена ДВС с КПП: $220 USD" in english_text

    assert parse_aed_price("15000") == Decimal("15000")
    assert parse_aed_price("199") == Decimal("199")
    assert parse_aed_price("102") == Decimal("102")
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
    assert "Продавец:" not in caption
    assert caption.endswith("—")

    moscow = ZoneInfo("Europe/Moscow")
    assert next_publication_slot(datetime(2026, 7, 13, 8, 29, tzinfo=moscow)).isoformat().startswith(
        "2026-07-13T09:00:00"
    )
    assert next_publication_slot(datetime(2026, 7, 13, 21, 31, tzinfo=moscow)).isoformat().startswith(
        "2026-07-13T22:00:00"
    )
    assert next_publication_slot(datetime(2026, 7, 13, 22, 1, tzinfo=moscow)).isoformat().startswith(
        "2026-07-13T22:30:00"
    )
    assert next_publication_slot(datetime(2026, 7, 13, 22, 31, tzinfo=moscow)).isoformat().startswith(
        "2026-07-14T09:00:00"
    )
    assert next_free_publication_slot(None, datetime(2026, 7, 13, 13, 8, tzinfo=moscow)).isoformat().startswith(
        "2026-07-13T13:30:00"
    )
    assert next_free_publication_slot(
        datetime(2026, 7, 13, 13, 30, tzinfo=moscow),
        datetime(2026, 7, 13, 13, 8, tzinfo=moscow),
    ).isoformat().startswith(
        "2026-07-13T14:00:00"
    )
    assert next_free_publication_slot(
        datetime(2026, 7, 13, 22, 30, tzinfo=moscow),
        datetime(2026, 7, 13, 13, 8, tzinfo=moscow),
    ).isoformat().startswith(
        "2026-07-14T09:00:00"
    )
    assert queue_slot_interval().total_seconds() == 30 * 60
    assert duplicate_delay().total_seconds() == 7 * 24 * 60 * 60
    assert TEST_QUEUE_INTERVAL.total_seconds() == 60
    assert TEST_DUPLICATE_DELAY.total_seconds() == 3 * 60
    assert isinstance(publication_channel_id(), int)


def test_queue_statistics_counts_first_publication_and_duplicates_separately() -> None:
    """Статистика очереди должна разделять первую публикацию и дубли."""
    database_source = Path("database.py").read_text(encoding="utf-8")
    assert "COUNT(*) FILTER (WHERE status = 'queued' AND published_at IS NULL) as total" in database_source
    assert "status IN ('published', 'duplicate_publishing')" in database_source
    assert "published_at IS NOT NULL" in database_source
    assert "duplicate_due_at > NOW()" in database_source


if __name__ == "__main__":
    test_main_menus_and_localization()
    test_prices_text_and_slots()
    test_premium_emoji_html()
    test_queue_statistics_counts_first_publication_and_duplicates_separately()
    asyncio.run(test_video_chunks())
    print("Smoke checks passed.")
