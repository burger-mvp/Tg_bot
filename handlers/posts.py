"""Создание постов, модерация супер-администратором и постановка в очередь."""

import html
import logging

from typing import Any, Final
from uuid import UUID, uuid4

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import TELEGRAM_API_SERVER_URL, TEST_MODE
from roles import super_admin_ids
from database import (
    approve_post,
    create_post,
    get_post,
    get_user_language,
    get_user_phone_number,
    get_user_shop_name,
    reject_post,
    set_moderation_message,
    update_pending_post_text,
)
from keyboards import (
    cancel_keyboard,
    category_keyboard,
    engine_type_keyboard,
    main_menu,
    media_step_keyboard,
    moderation_keyboard,
)
from locales import SUPPORTED_LANGUAGE_CODES, normalize_language_code, t
from roles import get_role_from_db_or_config, is_super_admin
from scheduler.post_scheduler import next_publication_slot
from utils.pricing import BODY_MARKUP, ENGINE_MARKUP, format_post_text, parse_aed_price, serialize_price
from utils.publishing import send_queued_post


router = Router(name=__name__)
logger = logging.getLogger(__name__)
MAX_MEDIA_FILES: Final = 30
MAX_MEDIA_FILE_SIZE_BYTES: Final = 20 * 1024 * 1024
MAX_LOCAL_API_MEDIA_FILE_SIZE_BYTES: Final = 2_000 * 1_000_000
MAX_DESCRIPTION_LENGTH: Final = 4_000
CREATE_POST_TEXTS: Final = frozenset({
    "Создать пост", "Create post", "إنشاء منشور",
    "پست ایجاد کریں", "پوسٹ بنائیں", "पोस्ट बनाएं", "পোস্ট তৈরি করুন"
})
MEDIA_DONE_TEXTS: Final = frozenset({
    "✅ Медиа загружены", "✅ Media uploaded", "✅ تم تحميل الوسائط",
    "✅ رسانه آپلود شد", "✅ میڈیا اپ لوڈ ہوگیا", "✅ मीडिया अपलोड हुआ", "✅ মিডিয়া আপলোড হয়েছে"
})


class PostCreation(StatesGroup):
    """Шаги создания товарного поста для любого завершившего регистрацию пользователя."""

    waiting_for_media = State()
    waiting_for_category = State()
    waiting_for_engine_type = State()
    waiting_for_engine_price = State()
    waiting_for_transmission_price = State()
    waiting_for_description = State()
    waiting_for_body_description = State()
    waiting_for_body_price = State()


class ModerationEdit(StatesGroup):
    """Ожидание нового описания от супер-администратора."""

    waiting_for_description = State()


async def _registered_language(telegram_id: int) -> str | None:
    """Возвращает язык завершившего выбор пользователя или None."""
    language_code = await get_user_language(telegram_id)
    return language_code if language_code in SUPPORTED_LANGUAGE_CODES else None


async def _language_from_state_or_database(message: Message, state: FSMContext) -> str:
    """Определяет язык FSM, имея безопасный русский запасной вариант."""
    language_code = (await state.get_data()).get("language_code")
    if language_code in SUPPORTED_LANGUAGE_CODES:
        return language_code
    if message.from_user is not None:
        database_language = await _registered_language(message.from_user.id)
        if database_language is not None:
            return database_language
    return "ru"


async def _answer_with_cancel(message: Message, language_code: str, text_key: str, **kwargs: object) -> None:
    """Отправляет стандартное сообщение сценария с кнопкой отмены."""
    await message.answer(
        t(language_code, text_key, **kwargs),
        reply_markup=cancel_keyboard(language_code),
    )


def _price_data(data: dict[str, Any]) -> dict[str, Any]:
    """Извлекает рассчитанные цены из FSM, защищаясь от поврежденного состояния."""
    prices = data.get("price_data")
    return prices if isinstance(prices, dict) else {}


async def _save_media_item(
    message: Message,
    state: FSMContext,
    media_type: str,
    file_id: str,
    file_size: int | None,
) -> None:
    """Добавляет обычное видео или видео-файл к текущему создаваемому посту."""
    language_code = await _language_from_state_or_database(message, state)
    max_file_size = MAX_LOCAL_API_MEDIA_FILE_SIZE_BYTES if TELEGRAM_API_SERVER_URL else MAX_MEDIA_FILE_SIZE_BYTES
    max_file_size_mb = 2_000 if TELEGRAM_API_SERVER_URL else 20
    if file_size is not None and file_size > max_file_size:
        await message.answer(
            t(language_code, "media_too_large", max_size_mb=max_file_size_mb),
            reply_markup=media_step_keyboard(language_code),
        )
        return
    data = await state.get_data()
    media_items = data.get("media_items")
    if not isinstance(media_items, list):
        media_items = []
    if len(media_items) >= MAX_MEDIA_FILES:
        await message.answer(t(language_code, "media_limit", max_count=MAX_MEDIA_FILES))
        return

    media_items.append({"type": media_type, "file_id": file_id})
    await state.update_data(media_items=media_items)
    await message.answer(
        t(language_code, "media_saved", count=len(media_items), max_count=MAX_MEDIA_FILES),
        reply_markup=media_step_keyboard(language_code),
    )


async def _save_completed_post(message: Message, state: FSMContext, bot: Bot, description: str) -> None:
    """Собирает текст, сохраняет пост и направляет его в нужный бизнес-процесс."""
    if message.from_user is None:
        return

    data = await state.get_data()
    language_code = normalize_language_code(data.get("language_code"))
    media_items = data.get("media_items")
    post_kind = data.get("post_kind")
    price_data = _price_data(data)
    if (
        not isinstance(media_items, list)
        or not media_items
        or not isinstance(post_kind, str)
        or not price_data
    ):
        await state.clear()
        await message.answer(t(language_code, "post_cancelled"))
        return

    role = await get_role_from_db_or_config(message.from_user.id)
    shop_name = await get_user_shop_name(message.from_user.id) or ""
    post_text = format_post_text(description, post_kind, price_data, seller_name=shop_name, language_code=language_code)
    post_id = uuid4()
    # В тестовом режиме модерацию обходим, чтобы можно было быстро проверять публикации.
    status = "queued" if TEST_MODE or role in ("admin", "super_admin", "trusted_seller") else "pending_moderation"
    try:
        await create_post(
            post_id=post_id,
            author_telegram_id=message.from_user.id,
            author_role=role,
            language_code=language_code,
            media_items=[item for item in media_items if isinstance(item, dict)],
            description=description,
            post_kind=post_kind,
            price_data=price_data,
            post_text=post_text,
            status=status,
            scheduled_at=next_publication_slot(),
        )
    except Exception:
        logger.exception("Не удалось сохранить пост пользователя %s в post_queue", message.from_user.id)
        await message.answer(t(language_code, "post_save_failed"))
        return
    await state.clear()

    if status == "queued":
        await message.answer(
            t(language_code, "post_added_queue"),
            reply_markup=main_menu(role, language_code),
        )
        return

    try:
        post = await get_post(post_id)
    except Exception:
        logger.exception("Не удалось прочитать сохраненный пост %s для модерации", post_id)
        await message.answer(t(language_code, "post_save_failed"))
        return
    if post is None:
        await message.answer(t(language_code, "moderation_delivery_failed"))
        return
    try:
        # Отправляем уведомление только супер-админам
        for admin_id in super_admin_ids():
            try:
                await bot.send_message(
                    admin_id,
                    t(language_code, "moderation_request", author_id=message.from_user.id),
                )
                moderation_messages = await send_queued_post(
                    bot,
                    admin_id,
                    post,
                    text_reply_markup=moderation_keyboard(str(post_id), language_code),
                )
                moderation_message = moderation_messages[-1]
                await set_moderation_message(post_id, moderation_message.chat.id, moderation_message.message_id)
            except TelegramAPIError:
                logger.exception("Не удалось отправить модерацию админу %s", admin_id)
    except Exception:
        await message.answer(t(language_code, "moderation_delivery_failed"))
        return

    await message.answer(
        t(language_code, "post_sent_for_moderation"),
        reply_markup=main_menu(role, language_code),
    )


async def _finish_description(message: Message, state: FSMContext, bot: Bot) -> None:
    """Проверяет описание и завершает создание поста."""
    if message.text is None:
        return
    language_code = await _language_from_state_or_database(message, state)
    description = message.text.strip()
    if not description:
        await _answer_with_cancel(message, language_code, "description_empty")
        return
    if len(description) > MAX_DESCRIPTION_LENGTH:
        await _answer_with_cancel(
            message,
            language_code,
            "description_too_long",
            max_length=MAX_DESCRIPTION_LENGTH,
        )
        return
    await _save_completed_post(message, state, bot, description)


@router.message(F.text.in_(CREATE_POST_TEXTS))
async def start_post_creation(message: Message, state: FSMContext) -> None:
    """Запускает общий сценарий создания поста из главного меню."""
    if message.from_user is None:
        return
    language_code = await _registered_language(message.from_user.id)
    if language_code is None or not await get_user_phone_number(message.from_user.id):
        await message.answer(t("ru", "language_required"))
        return

    await state.clear()
    await state.set_state(PostCreation.waiting_for_media)
    await state.update_data(language_code=language_code, media_items=[])
    await message.answer(t(language_code, "send_media"), reply_markup=media_step_keyboard(language_code))


@router.message(PostCreation.waiting_for_media, F.text.in_(MEDIA_DONE_TEXTS))
async def finish_media_collection(message: Message, state: FSMContext) -> None:
    """Завершает ручной сбор медиа и показывает выбор категории."""
    if message.from_user is None:
        return
    language_code = normalize_language_code((await state.get_data()).get("language_code"))
    media_items = (await state.get_data()).get("media_items")
    if not isinstance(media_items, list) or not media_items:
        # Пользователь нажал кнопку, но не загрузил медиа — остаёмся в том же состоянии.
        await message.answer(
            t(language_code, "no_media"),
            reply_markup=media_step_keyboard(language_code),
        )
        return
    await state.set_state(PostCreation.waiting_for_category)
    role = await get_role_from_db_or_config(message.from_user.id)
    await message.answer(t(language_code, "media_collection_complete"), reply_markup=main_menu(role, language_code))
    await message.answer(t(language_code, "choose_category"), reply_markup=category_keyboard(language_code))


@router.message(PostCreation.waiting_for_media, F.video)
async def collect_video(message: Message, state: FSMContext) -> None:
    """Добавляет каждое видео, включая элементы Telegram-альбомов, в FSM-список."""
    if message.video is None:
        return
    await _save_media_item(message, state, "video", message.video.file_id, message.video.file_size)


@router.message(PostCreation.waiting_for_media, F.photo)
async def collect_photo(message: Message, state: FSMContext) -> None:
    """Добавляет фотографии в список медиа."""
    if message.photo is None or not message.photo:
        return
    # Берём самое большое разрешение
    largest_photo = message.photo[-1]
    await _save_media_item(message, state, "photo", largest_photo.file_id, largest_photo.file_size)


@router.message(PostCreation.waiting_for_media, F.document)
async def collect_video_document(message: Message, state: FSMContext) -> None:
    """Принимает MP4/MOV и другие видео, отправленные Telegram как файл."""
    if message.document is None:
        return
    mime_type = message.document.mime_type or ""
    filename = (message.document.file_name or "").lower()
    is_video_file = mime_type.startswith("video/") or filename.endswith((".mp4", ".mov", ".mkv", ".avi", ".webm"))
    if not is_video_file:
        language_code = await _language_from_state_or_database(message, state)
        await message.answer(t(language_code, "send_media_only"), reply_markup=media_step_keyboard(language_code))
        return
    await _save_media_item(message, state, "document", message.document.file_id, message.document.file_size)


@router.message(PostCreation.waiting_for_media)
async def reject_non_video(message: Message, state: FSMContext) -> None:
    """Не позволяет перейти дальше с текстом или неподдерживаемым вложением."""
    language_code = await _language_from_state_or_database(message, state)
    await message.answer(t(language_code, "media_expected"), reply_markup=media_step_keyboard(language_code))


@router.message(F.video)
@router.message(F.document)
@router.message(F.animation)
@router.message(F.video_note)
async def explain_media_outside_post_creation(message: Message, state: FSMContext) -> None:
    """Не оставляет без ответа медиа, присланное без активного шага загрузки."""
    if message.from_user is None:
        return

    current_state = await state.get_state()
    language_code = await _registered_language(message.from_user.id) or "ru"
    logger.warning(
        "Медиа вне шага загрузки: user_id=%s, state=%s, content_type=%s",
        message.from_user.id,
        current_state,
        message.content_type,
    )
    if current_state is None:
        await message.answer(t(language_code, "media_outside_post_creation"))
        return
    await message.answer(t(language_code, "media_not_expected"))


@router.callback_query(PostCreation.waiting_for_category, F.data == "post:category:engine")
async def select_engine_category(callback: CallbackQuery, state: FSMContext) -> None:
    """Переходит от категории ДВС к выбору комплектации."""
    if callback.message is None:
        return
    language_code = normalize_language_code((await state.get_data()).get("language_code"))
    await callback.answer()
    await state.set_state(PostCreation.waiting_for_engine_type)
    await callback.message.answer(
        t(language_code, "choose_engine_type"),
        reply_markup=engine_type_keyboard(language_code),
    )


@router.callback_query(PostCreation.waiting_for_category, F.data == "post:category:body")
async def select_body_category(callback: CallbackQuery, state: FSMContext) -> None:
    """Для кузовного товара сначала запрашивает описание."""
    if callback.message is None:
        return
    language_code = normalize_language_code((await state.get_data()).get("language_code"))
    await callback.answer()
    await state.update_data(post_kind="body")
    await state.set_state(PostCreation.waiting_for_body_description)
    await _answer_with_cancel(callback.message, language_code, "enter_body_description")


@router.callback_query(PostCreation.waiting_for_engine_type, F.data == "post:engine:only")
async def select_engine_only(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбирает сценарий с одной ценой ДВС."""
    if callback.message is None:
        return
    language_code = normalize_language_code((await state.get_data()).get("language_code"))
    await callback.answer()
    await state.update_data(post_kind="engine_only")
    await state.set_state(PostCreation.waiting_for_engine_price)
    await _answer_with_cancel(callback.message, language_code, "enter_engine_price")


@router.callback_query(PostCreation.waiting_for_engine_type, F.data == "post:engine:transmission")
async def select_engine_with_transmission(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбирает сценарий с ценами отдельного ДВС и ДВС с КПП."""
    if callback.message is None:
        return
    language_code = normalize_language_code((await state.get_data()).get("language_code"))
    await callback.answer()
    await state.update_data(post_kind="engine_with_transmission")
    await state.set_state(PostCreation.waiting_for_engine_price)
    await _answer_with_cancel(callback.message, language_code, "enter_engine_price")


@router.message(PostCreation.waiting_for_engine_price, F.text)
async def receive_engine_price(message: Message, state: FSMContext) -> None:
    """Сохраняет цену двигателя и выбирает следующий требуемый шаг."""
    language_code = await _language_from_state_or_database(message, state)
    try:
        price = parse_aed_price(message.text or "")
    except ValueError:
        await _answer_with_cancel(message, language_code, "invalid_price")
        return

    data = await state.get_data()
    prices = _price_data(data)
    prices["engine"] = serialize_price(price, ENGINE_MARKUP)
    await state.update_data(price_data=prices)
    if data.get("post_kind") == "engine_with_transmission":
        await state.set_state(PostCreation.waiting_for_transmission_price)
        await _answer_with_cancel(message, language_code, "enter_transmission_price")
        return
    await state.set_state(PostCreation.waiting_for_description)
    await _answer_with_cancel(message, language_code, "enter_description")


@router.message(PostCreation.waiting_for_transmission_price, F.text)
async def receive_transmission_price(message: Message, state: FSMContext) -> None:
    """Сохраняет вторую цену ДВС с КПП, затем запрашивает описание."""
    language_code = await _language_from_state_or_database(message, state)
    try:
        price = parse_aed_price(message.text or "")
    except ValueError:
        await _answer_with_cancel(message, language_code, "invalid_price")
        return

    prices = _price_data(await state.get_data())
    prices["engine_with_transmission"] = serialize_price(price, ENGINE_MARKUP)
    await state.update_data(price_data=prices)
    await state.set_state(PostCreation.waiting_for_description)
    await _answer_with_cancel(message, language_code, "enter_description")


@router.message(PostCreation.waiting_for_description, F.text)
async def receive_engine_description(message: Message, state: FSMContext, bot: Bot) -> None:
    """Завершает создание поста категории ДВС."""
    await _finish_description(message, state, bot)


@router.message(PostCreation.waiting_for_body_description, F.text)
async def receive_body_description(message: Message, state: FSMContext) -> None:
    """Для кузовного товара сохраняет описание до ввода цены."""
    language_code = await _language_from_state_or_database(message, state)
    description = (message.text or "").strip()
    if not description:
        await _answer_with_cancel(message, language_code, "description_empty")
        return
    if len(description) > MAX_DESCRIPTION_LENGTH:
        await _answer_with_cancel(
            message,
            language_code,
            "description_too_long",
            max_length=MAX_DESCRIPTION_LENGTH,
        )
        return
    await state.update_data(description=description)
    await state.set_state(PostCreation.waiting_for_body_price)
    await _answer_with_cancel(message, language_code, "enter_body_price")


@router.message(PostCreation.waiting_for_body_price, F.text)
async def receive_body_price(message: Message, state: FSMContext, bot: Bot) -> None:
    """Рассчитывает цену кузовной детали с наценкой 15% и сохраняет пост."""
    language_code = await _language_from_state_or_database(message, state)
    try:
        price = parse_aed_price(message.text or "")
    except ValueError:
        await _answer_with_cancel(message, language_code, "invalid_price")
        return

    data = await state.get_data()
    description = data.get("description")
    if not isinstance(description, str):
        await state.clear()
        await message.answer(t(language_code, "post_cancelled"))
        return
    prices = _price_data(data)
    prices["body"] = serialize_price(price, BODY_MARKUP)
    await state.update_data(price_data=prices)
    await _save_completed_post(message, state, bot, description)


@router.message(
    PostCreation.waiting_for_engine_price,
    PostCreation.waiting_for_transmission_price,
    PostCreation.waiting_for_body_price,
)
async def reject_non_text_price(message: Message, state: FSMContext) -> None:
    """На шагах цены не принимает стикеры и другие нетекстовые сообщения."""
    language_code = await _language_from_state_or_database(message, state)
    await _answer_with_cancel(message, language_code, "invalid_price")


@router.message(
    PostCreation.waiting_for_engine_price,
    PostCreation.waiting_for_transmission_price,
    PostCreation.waiting_for_description,
    PostCreation.waiting_for_body_description,
    PostCreation.waiting_for_body_price,
)
async def reject_non_text_post_value(message: Message, state: FSMContext) -> None:
    """Не принимает вложения на шагах цены и описания."""
    language_code = await _language_from_state_or_database(message, state)
    await _answer_with_cancel(message, language_code, "send_text_only")


@router.callback_query(F.data == "post:cancel")
async def cancel_post_creation(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменяет активный сценарий создания поста."""
    if await state.get_state() is None:
        await callback.answer()
        return
    language_code = normalize_language_code((await state.get_data()).get("language_code"))
    await state.clear()
    await callback.answer(t(language_code, "post_cancelled"))
    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
        role = await get_role_from_db_or_config(callback.from_user.id)
        await callback.message.answer(t(language_code, "post_cancelled"), reply_markup=main_menu(role, language_code))


def _post_id_from_callback(callback: CallbackQuery, action: str) -> UUID | None:
    """Извлекает UUID поста из callback_data ожидаемого формата."""
    if callback.data is None:
        return None
    prefix = f"moderation:{action}:"
    if not callback.data.startswith(prefix):
        return None
    try:
        return UUID(callback.data.removeprefix(prefix))
    except ValueError:
        return None


async def _require_super_admin(callback: CallbackQuery) -> bool:
    """Ограничивает модерацию только супер-администраторами."""
    if is_super_admin(callback.from_user.id):
        return True
    await callback.answer(t("ru", "access_denied"), show_alert=True)
    return False


@router.callback_query(F.data.startswith("moderation:approve:"))
async def approve_moderated_post(callback: CallbackQuery) -> None:
    """Одобряет пост обычного пользователя и переносит его в очередь."""
    answered = False
    post_id: UUID | None = None
    try:
        if not await _require_super_admin(callback):
            answered = True
            return
        post_id = _post_id_from_callback(callback, "approve")
        if post_id is None:
            await callback.answer(t("ru", "already_moderated"), show_alert=True)
            answered = True
            return
        post = await approve_post(post_id, next_publication_slot())
        if post is None:
            await callback.answer(t("ru", "already_moderated"), show_alert=True)
            answered = True
            return
        await callback.answer(t(post.language_code, "moderation_approved"))
        answered = True
        if callback.message is not None:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass
            await callback.message.answer(t(post.language_code, "moderation_approved"))
    except Exception as error:
        logger.exception("Не удалось одобрить пост по callback %s", callback.data)
        language_code = "ru"
        if post_id is not None:
            failed_post = await get_post(post_id)
            if failed_post is not None:
                language_code = failed_post.language_code
        if not answered:
            await callback.answer(t(language_code, "moderation_approve_failed"), show_alert=True)
            answered = True
        if callback.message is not None:
            await callback.message.answer(t(language_code, "moderation_approve_failed_detail", error=error))
    finally:
        if not answered:
            await callback.answer()


@router.callback_query(F.data.startswith("moderation:reject:"))
async def reject_moderated_post(callback: CallbackQuery, bot: Bot) -> None:
    """Отклоняет пост и уведомляет автора."""
    if not await _require_super_admin(callback):
        return
    post_id = _post_id_from_callback(callback, "reject")
    if post_id is None:
        await callback.answer(t("ru", "already_moderated"), show_alert=True)
        return
    
    result = await reject_post(post_id)
    if result is None:
        await callback.answer(t("ru", "already_moderated"), show_alert=True)
        return
    
    author_telegram_id, shop_name = result
    await callback.answer(t("ru", "post_rejected"))
    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
        await callback.message.answer(t("ru", "post_rejected"))
    
    # Уведомляем автора
    author_language = await get_user_language(author_telegram_id) or "ru"
    try:
        await bot.send_message(
            author_telegram_id,
            t(author_language, "post_rejected_notification"),
        )
    except TelegramAPIError:
        logger.warning("Не удалось уведомить автора %s об отклонении поста", author_telegram_id)


@router.callback_query(F.data.startswith("moderation:edit:"))
async def start_moderation_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрашивает у супер-администратора новое описание ожидающего поста."""
    if not await _require_super_admin(callback):
        return
    post_id = _post_id_from_callback(callback, "edit")
    post = await get_post(post_id) if post_id is not None else None
    if post is None or post.status != "pending_moderation":
        await callback.answer(t("ru", "already_moderated"), show_alert=True)
        return
    await state.clear()
    await state.set_state(ModerationEdit.waiting_for_description)
    await state.update_data(post_id=str(post.id), language_code=post.language_code)
    await callback.answer()
    if callback.message is not None:
        escaped_description = html.escape(post.description)
        await callback.message.answer(
            t(post.language_code, "edit_prompt_with_description", description=escaped_description),
            reply_markup=cancel_keyboard(post.language_code),
            parse_mode="HTML",
        )


@router.message(ModerationEdit.waiting_for_description, F.text)
async def save_moderation_edit(message: Message, state: FSMContext, bot: Bot) -> None:
    """Сохраняет новую редакцию и повторно показывает её администратору."""
    if message.from_user is None or not is_super_admin(message.from_user.id):
        await state.clear()
        await message.answer(t("ru", "access_denied"))
        return
    language_code = await _language_from_state_or_database(message, state)
    description = (message.text or "").strip()
    if not description:
        await _answer_with_cancel(message, language_code, "description_empty")
        return
    if len(description) > MAX_DESCRIPTION_LENGTH:
        await _answer_with_cancel(
            message,
            language_code,
            "description_too_long",
            max_length=MAX_DESCRIPTION_LENGTH,
        )
        return
    post_id_raw = (await state.get_data()).get("post_id")
    try:
        post_id = UUID(str(post_id_raw))
    except ValueError:
        await state.clear()
        await message.answer(t(language_code, "already_moderated"))
        return
    original_post = await get_post(post_id)
    if original_post is None or original_post.status != "pending_moderation":
        await state.clear()
        await message.answer(t(language_code, "already_moderated"))
        return
    post_text = format_post_text(
        description,
        original_post.post_kind,
        original_post.price_data,
        seller_name=original_post.author_shop_name,
        language_code=original_post.language_code,
    )
    updated_post = await update_pending_post_text(post_id, description, post_text)
    await state.clear()
    if updated_post is None:
        await message.answer(t(language_code, "already_moderated"))
        return
    try:
        # Сразу показываем обновленный пост админу, который редактировал описание.
        await message.answer(t(updated_post.language_code, "post_updated"))
        moderation_messages = await send_queued_post(
            bot,
            message.chat.id,
            updated_post,
            text_reply_markup=moderation_keyboard(str(updated_post.id), updated_post.language_code),
        )
        moderation_message = moderation_messages[-1]
        await set_moderation_message(
            updated_post.id,
            moderation_message.chat.id,
            moderation_message.message_id,
        )

        # Остальным супер-админам тоже отправляем обновленную версию.
        for admin_id in super_admin_ids() - {message.chat.id}:
            try:
                await bot.send_message(
                    admin_id,
                    t(updated_post.language_code, "moderation_request", author_id=updated_post.author_telegram_id),
                )
                other_messages = await send_queued_post(
                    bot,
                    admin_id,
                    updated_post,
                    text_reply_markup=moderation_keyboard(str(updated_post.id), updated_post.language_code),
                )
                other_message = other_messages[-1]
                await set_moderation_message(
                    updated_post.id,
                    other_message.chat.id,
                    other_message.message_id,
                )
            except TelegramAPIError:
                logger.exception("Не удалось отправить обновленную модерацию админу %s", admin_id)
    except Exception:
        logger.exception("Не удалось повторно отправить обновленный пост %s на модерацию", updated_post.id)
        await message.answer(t(language_code, "moderation_delivery_failed"))
        return


@router.message(ModerationEdit.waiting_for_description)
async def reject_non_text_moderation_edit(message: Message, state: FSMContext) -> None:
    """Не позволяет заменить описание медиа-вложением."""
    language_code = await _language_from_state_or_database(message, state)
    await _answer_with_cancel(message, language_code, "send_text_only")
