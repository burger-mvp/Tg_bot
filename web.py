"""Простой сайт объявлений и админка."""

from __future__ import annotations

import html
import logging
import re
import asyncio
from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import (
    S3_ACCESS_KEY_ID,
    S3_BUCKET_NAME,
    S3_ENDPOINT_URL,
    S3_REGION,
    S3_SECRET_ACCESS_KEY,
    SALES_MANAGER_IDS,
    TOKEN,
    WEB_ADMIN_PASSWORD,
    WEB_LISTING_RETENTION_DAYS,
    WEB_PUBLIC_URL,
    WEB_SYNC_API_KEY,
)
from database import (
    close_db,
    create_purchase_request,
    create_web_listing_from_payload,
    get_web_listing,
    get_web_listings,
    init_db,
    mark_purchase_request_notified,
    set_web_listing_status,
)


logger = logging.getLogger(__name__)
app = FastAPI(title="KPP Motors Listings")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
_PHONE_RE = re.compile(r"^[0-9+()\-\s]{6,32}$")


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


def _base_url(request: Request) -> str:
    return WEB_PUBLIC_URL or str(request.base_url).rstrip("/")


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


def _admin_allowed(password: str | None = None) -> None:
    if WEB_ADMIN_PASSWORD is None:
        raise HTTPException(status_code=403, detail="WEB_ADMIN_PASSWORD не задан.")
    if password != WEB_ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Неверный пароль.")


async def _notify_sales_managers(listing: dict, phone_number: str, request_id: int, request: Request) -> None:
    if not SALES_MANAGER_IDS:
        logger.warning("SALES_MANAGER_IDS не задан, заявка %s сохранена без Telegram-уведомления", request_id)
        return

    listing_url = f"{_base_url(request)}/listing/{listing['id']}"
    text = (
        "🛒 Новая заявка с сайта\n\n"
        f"Телефон клиента: {html.escape(phone_number)}\n"
        f"Цена: ${listing['price_usd']} USD\n"
        f"Магазин: {html.escape(listing['seller_shop_name'])}\n\n"
        f"Объявление: {listing_url}\n\n"
        f"Описание: {html.escape(str(listing['description'])[:500])}"
    )
    bot = Bot(token=TOKEN)
    try:
        for manager_id in SALES_MANAGER_IDS:
            try:
                await bot.send_message(manager_id, text)
            except TelegramAPIError:
                logger.exception("Не удалось отправить заявку %s менеджеру %s", request_id, manager_id)
        await mark_purchase_request_notified(request_id)
    finally:
        await bot.session.close()


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
    return templates.TemplateResponse(request, "listing.html", {"listing": listing})


@app.post("/listing/{listing_id}/buy")
async def buy_listing(request: Request, listing_id: UUID, phone_number: str = Form(...)) -> RedirectResponse:
    listing = await get_web_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    phone = phone_number.strip()
    if not _PHONE_RE.fullmatch(phone):
        return RedirectResponse(f"/listing/{listing_id}?error=phone", status_code=303)
    request_id = await create_purchase_request(listing_id, phone)
    await _notify_sales_managers(listing, phone, request_id, request)
    return RedirectResponse(f"/listing/{listing_id}?sent=1", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin_login.html")


@app.post("/admin", response_class=HTMLResponse)
async def admin_listings(request: Request, password: str = Form(...)) -> HTMLResponse:
    _admin_allowed(password)
    listings = await get_web_listings(limit=300, include_hidden=True)
    return templates.TemplateResponse(
        request,
        "admin.html",
        {"listings": listings, "password": password},
    )


@app.post("/admin/listing/{listing_id}/status")
async def admin_set_status(
    listing_id: UUID,
    password: str = Form(...),
    status: str = Form(...),
) -> RedirectResponse:
    _admin_allowed(password)
    if status not in {"active", "hidden", "archived"}:
        raise HTTPException(status_code=400, detail="Некорректный статус")
    if not await set_web_listing_status(listing_id, status):
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    return RedirectResponse("/admin", status_code=303)
