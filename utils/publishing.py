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
    media_items: Sequence[dict[str, str]],
    post_text: str,
    text_reply_markup: InlineKeyboardMarkup | None = None,
) -> list[Message]:
    """Отправляет видеоальбомы и видео-файлы, затем отдельным сообщением итоговый текст."""
    sent_messages: list[Message] = []
    video_file_ids: list[str] = []

    async def send_video_chunk() -> None:
        """Отправляет накопленные обычные видео: одиночное или альбом до 10 элементов."""
        if not video_file_ids:
            return
        chunk = video_file_ids.copy()
        video_file_ids.clear()
        if len(chunk) == 1:
            sent_messages.append(await bot.send_video(chat_id, video=chunk[0]))
        else:
            media_group = [InputMediaVideo(media=file_id) for file_id in chunk]
            sent_messages.extend(await bot.send_media_group(chat_id, media=media_group))

    for item in media_items:
        item_type = item.get("type", "video")
        file_id = item.get("file_id")
        if not file_id:
            continue
        if item_type == "video":
            video_file_ids.append(file_id)
            if len(video_file_ids) == TELEGRAM_MEDIA_GROUP_LIMIT:
                await send_video_chunk()
            continue

        await send_video_chunk()
        sent_messages.append(await bot.send_document(chat_id, document=file_id))

    await send_video_chunk()
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
        post.media_items,
        post.post_text,
        text_reply_markup=text_reply_markup,
    )
