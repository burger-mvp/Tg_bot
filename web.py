"""Витрина объявлений и API синхронизации с Telegram-ботом."""

from __future__ import annotations

import logging
import asyncio
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import (
    S3_ACCESS_KEY_ID,
    S3_BUCKET_NAME,
    S3_ENDPOINT_URL,
    S3_REGION,
    S3_SECRET_ACCESS_KEY,
    SITE_CONTACT_MAX_URL,
    SITE_CONTACT_PHONE,
    SITE_CONTACT_TELEGRAM_URL,
    WEB_LISTING_RETENTION_DAYS,
    WEB_PUBLIC_URL,
    WEB_SYNC_API_KEY,
)
from database import (
    close_db,
    create_web_listing_from_payload,
    get_web_listing,
    get_web_listings,
    init_db,
    set_web_listing_status,
)


logger = logging.getLogger(__name__)
app = FastAPI(title="KPP Motors Listings")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
DELIVERY_TEXT = """Все запчасти согласовываются с вами в онлайн-режиме, что упрощает процесс. ‼️

Условия доставки:
🚨 ДВС, КПП и ходовая часть: 2,3$ за кг.
🚨 Кузовные детали, оптика, машинокомплекты — по запросу.
🚨 Запчасти для спецтехники Caterpillar, Komatsu, JCB — по запросу."""


def _s3_client():
    """Создает S3-compatible клиент для чтения приватных файлов Bucket."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        region_name=S3_REGION,
    )


def _media_content_type(object_key: str) -> str:
    """Определяет Content-Type по расширению сохраненного объекта."""
    lowered = object_key.lower()
    if lowered.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".mp4"):
        return "video/mp4"
    if lowered.endswith(".webm"):
        return "video/webm"
    return "application/octet-stream"


@app.on_event("startup")
async def startup() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    await init_db()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_db()


@app.get("/media/{object_key:path}")
async def bucket_media(object_key: str) -> Response:
    """Отдает файлы сайта из приватного Bucket через приложение."""
    if not object_key.startswith("listings/"):
        raise HTTPException(status_code=404, detail="Файл не найден")
    try:
        result = await asyncio.to_thread(
            _s3_client().get_object,
            Bucket=S3_BUCKET_NAME,
            Key=object_key,
        )
    except Exception as error:
        logger.warning("Не удалось прочитать файл Bucket %s: %s", object_key, error)
        raise HTTPException(status_code=404, detail="Файл не найден") from error
    data = await asyncio.to_thread(result["Body"].read)
    return Response(data, media_type=result.get("ContentType") or _media_content_type(object_key))


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    listings = await get_web_listings(limit=120)
    return templates.TemplateResponse(request, "index.html", {"listings": listings})


@app.post("/api/listings")
async def api_create_listing(payload: dict, x_site_api_key: str | None = Header(default=None)) -> dict[str, str]:
    """Принимает объявление от Railway-бота и сохраняет его в локальную базу сайта."""
    if WEB_SYNC_API_KEY is None:
        raise HTTPException(status_code=403, detail="WEB_SYNC_API_KEY не задан.")
    if x_site_api_key != WEB_SYNC_API_KEY:
        raise HTTPException(status_code=401, detail="Неверный API-ключ.")
    media = payload.get("media") or []
    if not media:
        raise HTTPException(status_code=400, detail="Нет медиа для объявления.")
    try:
        listing_id = await create_web_listing_from_payload(
            payload=payload,
            retention_days=WEB_LISTING_RETENTION_DAYS,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Некорректные данные объявления.") from error
    return {"status": "ok", "listing_id": str(listing_id)}


@app.get("/listing/{listing_id}", response_class=HTMLResponse)
async def listing_detail(request: Request, listing_id: UUID) -> HTMLResponse:
    listing = await get_web_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    return templates.TemplateResponse(
        request,
        "listing.html",
        {
            "listing": listing,
            "delivery_text": DELIVERY_TEXT,
            "contact_phone": SITE_CONTACT_PHONE,
            "telegram_url": SITE_CONTACT_TELEGRAM_URL,
            "max_url": SITE_CONTACT_MAX_URL,
        },
    )


@app.post("/api/listings/{listing_id}/hide")
async def api_hide_listing(listing_id: UUID, x_site_api_key: str | None = Header(default=None)) -> dict[str, str]:
    """Скрывает объявление по защищенному API для Telegram-бота."""
    if WEB_SYNC_API_KEY is None:
        raise HTTPException(status_code=403, detail="WEB_SYNC_API_KEY не задан.")
    if x_site_api_key != WEB_SYNC_API_KEY:
        raise HTTPException(status_code=401, detail="Неверный API-ключ.")
    if not await set_web_listing_status(listing_id, "hidden"):
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    return {"status": "ok"}
