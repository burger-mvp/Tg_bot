"""Единая отправка медиа и подписи публикации в Telegram."""

from collections.abc import Sequence
from typing import Final

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InputMediaVideo, Message

from database import QueuedPost
from utils.pricing import format_post_caption


TELEGRAM_MEDIA_GROUP_LIMIT: Final = 10


async def send_post_content(
    bot: Bot,
    chat_id: int,
    media_items: Sequence[dict[str, str]],
    post_text: str,
    text_reply_markup: InlineKeyboardMarkup | None = None,
) -> list[Message]:
    """Отправляет медиа с подписью у первого файла без отдельного текстового сообщения."""
    sent_messages: list[Message] = []
    video_file_ids: list[str] = []
    caption = post_text
    caption_sent = False
    caption_message: Message | None = None

    async def send_video_chunk() -> None:
        """Отправляет накопленные видео: одиночное или альбом до 10 элементов."""
        nonlocal caption_message, caption_sent
        if not video_file_ids:
            return
        chunk = video_file_ids.copy()
        video_file_ids.clear()
        chunk_caption = caption if not caption_sent else None
        if len(chunk) == 1:
            message = await bot.send_video(
                chat_id,
                video=chunk[0],
                caption=chunk_caption,
                reply_markup=text_reply_markup if not caption_sent else None,
            )
            sent_messages.append(message)
            if not caption_sent:
                caption_message = message
        else:
            media_group = [
                InputMediaVideo(media=file_id, caption=chunk_caption if index == 0 else None)
                for index, file_id in enumerate(chunk)
            ]
            messages = await bot.send_media_group(chat_id, media=media_group)
            sent_messages.extend(messages)
            if not caption_sent:
                caption_message = messages[0]
        caption_sent = True

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
        document_caption = caption if not caption_sent else None
        message = await bot.send_document(
            chat_id,
            document=file_id,
            caption=document_caption,
            reply_markup=text_reply_markup if not caption_sent else None,
        )
        sent_messages.append(message)
        if not caption_sent:
            caption_message = message
            caption_sent = True

    await send_video_chunk()
    if text_reply_markup is not None and caption_message is not None and len(sent_messages) > 1:
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=caption_message.message_id,
            reply_markup=text_reply_markup,
        )
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
        format_post_caption(post.description, post.post_kind, post.price_data),
        text_reply_markup=text_reply_markup,
    )
