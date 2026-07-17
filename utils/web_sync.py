"""Синхронизация опубликованных Telegram-постов с сайтом объявлений."""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from uuid import uuid4

from aiogram import Bot

from config import (
    S3_ACCESS_KEY_ID,
    S3_BUCKET_NAME,
    S3_ENDPOINT_URL,
    S3_REGION,
    S3_SECRET_ACCESS_KEY,
    WEB_INTEGRATION_ENABLED,
    WEB_LISTING_RETENTION_DAYS,
)
from database import QueuedPost, create_web_listing


logger = logging.getLogger(__name__)


def _s3_client():
    """Создает S3-compatible клиент для Railway Bucket."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        region_name=S3_REGION,
    )


def _extension(media_type: str) -> str:
    """Возвращает безопасное расширение по типу Telegram-медиа."""
    if media_type == "photo":
        return "jpg"
    if media_type == "video":
        return "mp4"
    return "bin"


def _content_type(media_type: str) -> str:
    """Возвращает Content-Type для отдачи файлов на сайте."""
    if media_type == "photo":
        return "image/jpeg"
    if media_type == "video":
        return "video/mp4"
    return "application/octet-stream"


async def _download_telegram_file(bot: Bot, file_id: str) -> bytes:
    """Скачивает Telegram-файл в память."""
    buffer = BytesIO()
    await bot.download(file_id, destination=buffer)
    return buffer.getvalue()


async def _upload_to_bucket(object_key: str, data: bytes, media_type: str) -> None:
    """Загружает файл в Bucket без блокировки event loop."""
    client = _s3_client()
    await asyncio.to_thread(
        client.put_object,
        Bucket=S3_BUCKET_NAME,
        Key=object_key,
        Body=data,
        ContentType=_content_type(media_type),
    )


async def publish_post_to_web(bot: Bot, post: QueuedPost) -> None:
    """Создает объявление сайта с теми же медиа, что опубликованы в Telegram."""
    if not WEB_INTEGRATION_ENABLED:
        logger.info("Сайт/Bucket не настроены, синхронизация объявления %s пропущена.", post.id)
        return

    listing_id = uuid4()
    uploaded_media: list[dict[str, str]] = []
    for index, media_item in enumerate(post.media_items):
        file_id = media_item.get("file_id")
        if not file_id:
            continue
        media_type = media_item.get("type", "video")
        object_key = f"listings/{listing_id}/{index:02d}.{_extension(media_type)}"
        data = await _download_telegram_file(bot, file_id)
        await _upload_to_bucket(object_key, data, media_type)
        uploaded_media.append(
            {
                "media_type": media_type,
                "url": f"/media/{object_key}",
                "object_key": object_key,
            }
        )

    if not uploaded_media:
        logger.warning("У поста %s нет медиа для сайта, объявление не создано.", post.id)
        return

    await create_web_listing(
        listing_id=listing_id,
        post=post,
        media=uploaded_media,
        retention_days=WEB_LISTING_RETENTION_DAYS,
    )
