"""Единая отправка видео и итогового текста в Telegram."""

from collections.abc import Sequence
from typing import Final

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InputMediaVideo, Message

from database import QueuedPost


TELEGRAM_MEDIA_GROUP_LIMIT: Final = 10


async def send_post_content(
    bot: Bot,
    chat_id: int,
    media_file_ids: Sequence[str],
    post_text: str,
    text_reply_markup: InlineKeyboardMarkup | None = None,
) -> list[Message]:
    """Отправляет до 30 видео частями по 10, затем отдельным сообщением итоговый текст."""
    sent_messages: list[Message] = []
    for offset in range(0, len(media_file_ids), TELEGRAM_MEDIA_GROUP_LIMIT):
        chunk = media_file_ids[offset : offset + TELEGRAM_MEDIA_GROUP_LIMIT]
        if len(chunk) == 1:
            sent_messages.append(await bot.send_video(chat_id, video=chunk[0]))
        else:
            media_group = [InputMediaVideo(media=file_id) for file_id in chunk]
            sent_messages.extend(await bot.send_media_group(chat_id, media=media_group))
    sent_messages.append(await bot.send_message(chat_id, post_text, reply_markup=text_reply_markup))
    return sent_messages


async def send_queued_post(
    bot: Bot,
    chat_id: int,
    post: QueuedPost,
    text_reply_markup: InlineKeyboardMarkup | None = None,
) -> list[Message]:
    """Отправляет содержимое модели очереди в указанный Telegram-чат."""
    return await send_post_content(
        bot,
        chat_id,
        post.media_file_ids,
        post.post_text,
        text_reply_markup=text_reply_markup,
    )
