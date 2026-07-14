"""Единая отправка медиа и подписи публикации в Telegram."""

from collections.abc import Sequence
from typing import Final

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, Message

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
    media_buffer: list[dict[str, str]] = []
    caption = post_text
    caption_sent = False
    media_group_sent = False
    caption_message: Message | None = None

    async def send_media_chunk() -> None:
        """Отправляет накопленные медиа: одиночное или альбом до 10 элементов."""
        nonlocal caption_message, caption_sent, media_group_sent
        if not media_buffer:
            return
        chunk = media_buffer.copy()
        media_buffer.clear()
        chunk_caption = caption if not caption_sent else None
        
        if len(chunk) == 1:
            item_type = chunk[0].get("type", "video")
            file_id = chunk[0]["file_id"]
            
            if item_type == "photo":
                message = await bot.send_photo(
                    chat_id,
                    photo=file_id,
                    caption=chunk_caption,
                    reply_markup=text_reply_markup if not caption_sent else None,
                )
            elif item_type == "document":
                message = await bot.send_document(
                    chat_id,
                    document=file_id,
                    caption=chunk_caption,
                    reply_markup=text_reply_markup if not caption_sent else None,
                )
            else:  # video
                message = await bot.send_video(
                    chat_id,
                    video=file_id,
                    caption=chunk_caption,
                    reply_markup=text_reply_markup if not caption_sent else None,
                )
            sent_messages.append(message)
            if not caption_sent:
                caption_message = message
        else:
            media_group_sent = True
            media_group = []
            for index, item in enumerate(chunk):
                item_type = item.get("type", "video")
                file_id = item["file_id"]
                item_caption = chunk_caption if index == 0 else None
                
                if item_type == "photo":
                    media_group.append(InputMediaPhoto(media=file_id, caption=item_caption))
                else:  # video or document - treat as video in media group
                    media_group.append(InputMediaVideo(media=file_id, caption=item_caption))
            
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
        
        # Фото и видео могут быть в одной группе, document отправляется отдельно
        if item_type in ("video", "photo"):
            media_buffer.append(item)
            if len(media_buffer) == TELEGRAM_MEDIA_GROUP_LIMIT:
                await send_media_chunk()
            continue

        # Отправляем накопленное перед document
        await send_media_chunk()
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

    await send_media_chunk()
    if text_reply_markup is not None and media_group_sent:
        control_message = await bot.send_message(
            chat_id,
            "Управление постом:",
            reply_markup=text_reply_markup,
        )
        sent_messages.append(control_message)
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
        format_post_caption(post.description, post.post_kind, post.price_data, seller_name=post.author_shop_name),
        text_reply_markup=text_reply_markup,
    )
