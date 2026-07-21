"""Небольшие обработчики административного меню."""

import csv
import io
import logging
import re
from datetime import datetime
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, Message

from config import SCHEDULER_TIMEZONE
from database import (
    find_user_for_role_assignment,
    get_all_users,
    get_posts_waiting_for_duplicate_details,
    get_queued_posts,
    get_queue_statistics,
    get_user_language,
    set_user_banned,
    set_user_admin,
    set_user_trusted_seller,
)
from keyboards import cancel_keyboard, main_menu
from locales import SUPPORTED_LANGUAGE_CODES, t
from roles import is_admin_or_higher, is_super_admin
from utils.web_sync import hide_listing_on_site


router = Router(name=__name__)
logger = logging.getLogger(__name__)
SET_TRUSTED_SELLER_TEXTS = frozenset({"🌟 Назначить доверенного продавца", "🌟 Assign trusted seller"})
SET_ADMIN_TEXTS = frozenset({"👤 Назначить администратора", "👤 Assign administrator"})
BAN_USER_TEXTS = frozenset({"🚫 Заблокировать пользователя", "🚫 Block user"})
UNBAN_USER_TEXTS = frozenset({"✅ Разблокировать пользователя", "✅ Unblock user"})
DELETE_WEB_LISTING_TEXTS = frozenset({"🗑 Удалить объявление с сайта", "🗑 Delete site listing"})
VIEW_QUEUE_TEXTS = frozenset({"📋 Просмотр очереди", "📋 View queue"})
EXPORT_USERS_TEXTS = frozenset({"📊 Выгрузить users", "📊 Export users"})
SUPER_ADMIN_ACTION_TEXTS = (
    SET_TRUSTED_SELLER_TEXTS
    | SET_ADMIN_TEXTS
    | BAN_USER_TEXTS
    | UNBAN_USER_TEXTS
    | DELETE_WEB_LISTING_TEXTS
    | VIEW_QUEUE_TEXTS
    | EXPORT_USERS_TEXTS
)
ADMIN_ACTION_TEXTS = BAN_USER_TEXTS | UNBAN_USER_TEXTS | DELETE_WEB_LISTING_TEXTS
LISTING_ID_RE = re.compile(r"/listing/([0-9a-fA-F-]{36})")


class TrustedSellerAssignment(StatesGroup):
    """Ожидание идентификатора пользователя для назначения доверенного продавца."""
    
    waiting_for_shop_name = State()


class AdminAssignment(StatesGroup):
    """Ожидание идентификатора пользователя для назначения администратора."""
    
    waiting_for_telegram_id = State()


class UserBanAssignment(StatesGroup):
    """Ожидание Telegram ID пользователя для блокировки или разблокировки."""

    waiting_for_ban_id = State()
    waiting_for_unban_id = State()


class WebListingDeletion(StatesGroup):
    """Ожидание ссылки на объявление сайта для скрытия."""

    waiting_for_listing_url = State()


def _telegram_id_from_command(message: Message) -> int | None:
    """Извлекает Telegram ID из команды вида /ban 123."""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return int(parts[1].strip())
    except ValueError:
        return None


async def _admin_language(message: Message) -> str:
    """Возвращает язык администратора с безопасным русским fallback."""
    if message.from_user is None:
        return "ru"
    language_code = await get_user_language(message.from_user.id)
    return language_code if language_code in SUPPORTED_LANGUAGE_CODES else "ru"


def _telegram_id_from_text(text: str | None) -> int | None:
    """Извлекает Telegram ID из обычного текстового ответа."""
    try:
        return int((text or "").strip())
    except ValueError:
        return None


async def _finish_ban_change(message: Message, state: FSMContext, is_banned: bool) -> None:
    """Применяет блокировку или разблокировку из FSM-сценария."""
    if message.from_user is None:
        return
    language_code = (await state.get_data()).get("language_code")
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = await _admin_language(message)

    if not await is_admin_or_higher(message.from_user.id):
        await state.clear()
        await message.answer(t(language_code, "access_denied"))
        return

    user_id = _telegram_id_from_text(message.text)
    if user_id is None:
        await message.answer(t(language_code, "ban_usage" if is_banned else "unban_usage"))
        return

    if not await set_user_banned(user_id, is_banned):
        await message.answer(t(language_code, "ban_user_not_found", user_id=user_id))
        return

    await state.clear()
    role = "super_admin" if is_super_admin(message.from_user.id) else "admin"
    await message.answer(
        t(language_code, "ban_success" if is_banned else "unban_success", user_id=user_id),
        reply_markup=main_menu(role, language_code),
    )


@router.message(Command("ban"))
async def ban_user_command(message: Message) -> None:
    """Блокирует пользователя по Telegram ID из личной команды администратора."""
    if message.from_user is None:
        return
    language_code = await _admin_language(message)
    if not await is_admin_or_higher(message.from_user.id):
        await message.answer(t(language_code, "access_denied"))
        return

    user_id = _telegram_id_from_command(message)
    if user_id is None:
        await message.answer(t(language_code, "ban_usage"))
        return

    if not await set_user_banned(user_id, True):
        await message.answer(t(language_code, "ban_user_not_found", user_id=user_id))
        return
    await message.answer(t(language_code, "ban_success", user_id=user_id))


@router.message(Command("unban"))
async def unban_user_command(message: Message) -> None:
    """Разблокирует пользователя по Telegram ID из личной команды администратора."""
    if message.from_user is None:
        return
    language_code = await _admin_language(message)
    if not await is_admin_or_higher(message.from_user.id):
        await message.answer(t(language_code, "access_denied"))
        return

    user_id = _telegram_id_from_command(message)
    if user_id is None:
        await message.answer(t(language_code, "unban_usage"))
        return

    if not await set_user_banned(user_id, False):
        await message.answer(t(language_code, "ban_user_not_found", user_id=user_id))
        return
    await message.answer(t(language_code, "unban_success", user_id=user_id))


@router.message(StateFilter("*"), F.text.in_(BAN_USER_TEXTS))
async def start_user_ban_assignment(message: Message, state: FSMContext) -> None:
    """Начинает блокировку пользователя по кнопке админского меню."""
    if message.from_user is None:
        return
    language_code = await _admin_language(message)
    if not await is_admin_or_higher(message.from_user.id):
        await message.answer(t(language_code, "access_denied"))
        return

    await state.clear()
    await state.set_state(UserBanAssignment.waiting_for_ban_id)
    await state.update_data(language_code=language_code)
    await message.answer(t(language_code, "enter_telegram_id_for_ban"), reply_markup=cancel_keyboard(language_code))


@router.message(StateFilter("*"), F.text.in_(UNBAN_USER_TEXTS))
async def start_user_unban_assignment(message: Message, state: FSMContext) -> None:
    """Начинает разблокировку пользователя по кнопке админского меню."""
    if message.from_user is None:
        return
    language_code = await _admin_language(message)
    if not await is_admin_or_higher(message.from_user.id):
        await message.answer(t(language_code, "access_denied"))
        return

    await state.clear()
    await state.set_state(UserBanAssignment.waiting_for_unban_id)
    await state.update_data(language_code=language_code)
    await message.answer(t(language_code, "enter_telegram_id_for_unban"), reply_markup=cancel_keyboard(language_code))


@router.message(UserBanAssignment.waiting_for_ban_id, F.text, ~F.text.in_(SUPER_ADMIN_ACTION_TEXTS | ADMIN_ACTION_TEXTS))
async def process_user_ban_id(message: Message, state: FSMContext) -> None:
    """Блокирует пользователя по Telegram ID из FSM-сценария."""
    await _finish_ban_change(message, state, True)


@router.message(UserBanAssignment.waiting_for_unban_id, F.text, ~F.text.in_(SUPER_ADMIN_ACTION_TEXTS | ADMIN_ACTION_TEXTS))
async def process_user_unban_id(message: Message, state: FSMContext) -> None:
    """Разблокирует пользователя по Telegram ID из FSM-сценария."""
    await _finish_ban_change(message, state, False)


@router.message(UserBanAssignment.waiting_for_ban_id)
async def reject_non_text_user_ban_id(message: Message, state: FSMContext) -> None:
    """Отклоняет нетекстовый ввод при блокировке пользователя."""
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    await message.answer(t(language_code, "enter_telegram_id_for_ban"))


@router.message(UserBanAssignment.waiting_for_unban_id)
async def reject_non_text_user_unban_id(message: Message, state: FSMContext) -> None:
    """Отклоняет нетекстовый ввод при разблокировке пользователя."""
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    await message.answer(t(language_code, "enter_telegram_id_for_unban"))


@router.message(StateFilter("*"), F.text.in_(SET_TRUSTED_SELLER_TEXTS))
async def start_trusted_seller_assignment(message: Message, state: FSMContext) -> None:
    """Начинает процесс назначения доверенного продавца."""
    if message.from_user is None:
        return
    
    if not is_super_admin(message.from_user.id):
        await message.answer(t("ru", "access_denied"))
        return
    
    language_code = await get_user_language(message.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = "ru"
    
    await state.clear()
    await state.set_state(TrustedSellerAssignment.waiting_for_shop_name)
    await state.update_data(language_code=language_code)
    
    await message.answer(
        t(language_code, "enter_shop_name_for_trust"),
        reply_markup=cancel_keyboard(language_code),
    )


@router.message(
    TrustedSellerAssignment.waiting_for_shop_name,
    F.text,
    ~F.text.in_(SUPER_ADMIN_ACTION_TEXTS),
)
async def process_shop_name_for_trusted(message: Message, state: FSMContext) -> None:
    """Назначает доверенного продавца по ID, username, имени или shop_name."""
    if message.from_user is None or message.text is None:
        return
    
    if not is_super_admin(message.from_user.id):
        await state.clear()
        await message.answer(t("ru", "access_denied"))
        return
    
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    user = await find_user_for_role_assignment(message.text)
    if user is None:
        await message.answer(t(language_code, "shop_not_found"))
        return
    telegram_id = int(user["telegram_id"])
    user_label = user.get("name") or user.get("username") or user.get("shop_name") or str(telegram_id)
    
    success = await set_user_trusted_seller(telegram_id)
    await state.clear()
    
    if success:
        await message.answer(
            t(language_code, "trusted_seller_assigned", user_label=user_label),
            reply_markup=main_menu("super_admin", language_code),
        )
    else:
        await message.answer(t(language_code, "shop_not_found"))


@router.message(
    TrustedSellerAssignment.waiting_for_shop_name,
    ~F.text.in_(SUPER_ADMIN_ACTION_TEXTS),
)
async def reject_non_text_shop_name(message: Message, state: FSMContext) -> None:
    """Отклоняет нетекстовый ввод при назначении доверенного продавца."""
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    await message.answer(t(language_code, "enter_shop_name_for_trust"))


@router.message(StateFilter("*"), F.text.in_(SET_ADMIN_TEXTS))
async def start_admin_assignment(message: Message, state: FSMContext) -> None:
    """Начинает процесс назначения администратора."""
    if message.from_user is None:
        return
    
    if not is_super_admin(message.from_user.id):
        await message.answer(t("ru", "access_denied"))
        return
    
    language_code = await get_user_language(message.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = "ru"
    
    await state.clear()
    await state.set_state(AdminAssignment.waiting_for_telegram_id)
    await state.update_data(language_code=language_code)
    
    await message.answer(
        t(language_code, "enter_telegram_id_for_admin"),
        reply_markup=cancel_keyboard(language_code),
    )


@router.message(
    AdminAssignment.waiting_for_telegram_id,
    F.text,
    ~F.text.in_(SUPER_ADMIN_ACTION_TEXTS),
)
async def process_telegram_id_for_admin(message: Message, state: FSMContext) -> None:
    """Назначает администратора по ID, username, имени или shop_name."""
    if message.from_user is None or message.text is None:
        return
    
    if not is_super_admin(message.from_user.id):
        await state.clear()
        await message.answer(t("ru", "access_denied"))
        return
    
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    
    user = await find_user_for_role_assignment(message.text)
    if user is None:
        await message.answer(t(language_code, "user_not_found"))
        return
    telegram_id = int(user["telegram_id"])
    user_label = user.get("name") or user.get("username") or user.get("shop_name") or str(telegram_id)
    
    # Назначаем роль admin
    success = await set_user_admin(telegram_id)
    await state.clear()
    
    if success:
        await message.answer(
            t(language_code, "admin_assigned", user_label=user_label),
            reply_markup=main_menu("super_admin", language_code),
        )
    else:
        await message.answer(t(language_code, "user_not_found"))


@router.message(
    AdminAssignment.waiting_for_telegram_id,
    ~F.text.in_(SUPER_ADMIN_ACTION_TEXTS),
)
async def reject_non_text_telegram_id(message: Message, state: FSMContext) -> None:
    """Отклоняет нетекстовый ввод при назначении администратора."""
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    await message.answer(t(language_code, "enter_telegram_id_for_admin"))


@router.message(StateFilter("*"), F.text.in_(DELETE_WEB_LISTING_TEXTS))
async def start_web_listing_deletion(message: Message, state: FSMContext) -> None:
    """Запрашивает ссылку на объявление сайта для скрытия."""
    if message.from_user is None:
        return
    language_code = await _admin_language(message)
    if not await is_admin_or_higher(message.from_user.id):
        await message.answer(t(language_code, "access_denied"))
        return

    await state.clear()
    await state.set_state(WebListingDeletion.waiting_for_listing_url)
    await state.update_data(language_code=language_code)
    await message.answer(t(language_code, "delete_web_listing_prompt"), reply_markup=cancel_keyboard(language_code))


@router.message(WebListingDeletion.waiting_for_listing_url, F.text, ~F.text.in_(SUPER_ADMIN_ACTION_TEXTS | ADMIN_ACTION_TEXTS))
async def process_web_listing_deletion(message: Message, state: FSMContext) -> None:
    """Скрывает объявление сайта по ссылке или UUID."""
    if message.from_user is None or message.text is None:
        return
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    if not await is_admin_or_higher(message.from_user.id):
        await state.clear()
        await message.answer(t(language_code, "access_denied"))
        return

    raw_value = message.text.strip()
    match = LISTING_ID_RE.search(raw_value)
    listing_id_text = match.group(1) if match else raw_value
    try:
        listing_id = str(UUID(listing_id_text))
    except ValueError:
        await message.answer(t(language_code, "delete_web_listing_invalid"))
        return

    try:
        hide_listing_on_site(listing_id)
    except Exception as error:
        logger.exception("Не удалось скрыть объявление сайта %s", listing_id)
        await message.answer(t(language_code, "delete_web_listing_failed", error=error))
        return

    await state.clear()
    role = "super_admin" if is_super_admin(message.from_user.id) else "admin"
    await message.answer(t(language_code, "delete_web_listing_success"), reply_markup=main_menu(role, language_code))


@router.message(WebListingDeletion.waiting_for_listing_url)
async def reject_non_text_web_listing_deletion(message: Message, state: FSMContext) -> None:
    """Просит прислать ссылку текстом."""
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    await message.answer(t(language_code, "delete_web_listing_prompt"))


@router.message(StateFilter("*"), F.text.in_(VIEW_QUEUE_TEXTS))
async def view_queue_status(message: Message, state: FSMContext) -> None:
    """Показывает статистику по очереди публикаций."""
    if message.from_user is None:
        return
    
    if not is_super_admin(message.from_user.id):
        await message.answer(t("ru", "access_denied"))
        return

    await state.clear()

    try:
        language_code = await get_user_language(message.from_user.id)
        if language_code not in SUPPORTED_LANGUAGE_CODES:
            language_code = "ru"

        stats = await get_queue_statistics()
        queued_posts = await get_queued_posts()
        duplicate_posts = await get_posts_waiting_for_duplicate_details()
        total_posts = stats.get("total", 0)
        queued = stats.get("queued", 0)
        published = stats.get("published", 0)
        waiting_duplicate = stats.get("waiting_duplicate", 0)

        if queued == 0 and waiting_duplicate == 0 and not queued_posts and not duplicate_posts:
            await message.answer(t(language_code, "publication_queue_empty"))
            return

        message_text = t(
            language_code,
            "queue_status",
            total=total_posts,
            queued=queued,
            published=published,
            waiting_duplicate=waiting_duplicate,
        )
        if queued_posts:
            queue_lines = [t(language_code, "queue_list_header")]
            for index, post in enumerate(queued_posts, start=1):
                queue_lines.append(
                    t(
                        language_code,
                        "queue_list_item",
                        index=index,
                        shop_name=post.author_shop_name or "—",
                        scheduled_at=post.scheduled_at.astimezone(SCHEDULER_TIMEZONE).strftime("%d.%m %H:%M"),
                        description=post.description[:80],
                    )
                )
            message_text = f"{message_text}\n\n" + "\n".join(queue_lines)

        if duplicate_posts:
            duplicate_lines = [t(language_code, "duplicate_list_header")]
            for index, post in enumerate(duplicate_posts, start=1):
                duplicate_due_at = post.duplicate_due_at or post.scheduled_at
                duplicate_lines.append(
                    t(
                        language_code,
                        "duplicate_list_item",
                        index=index,
                        shop_name=post.author_shop_name or "—",
                        duplicate_due_at=duplicate_due_at.astimezone(SCHEDULER_TIMEZONE).strftime("%d.%m %H:%M"),
                        description=post.description[:80],
                    )
                )
            message_text = f"{message_text}\n\n" + "\n".join(duplicate_lines)

        await message.answer(message_text)
    except Exception as error:
        logger.exception("Ошибка при выводе очереди для супер-админа %s", message.from_user.id)
        await message.answer(f"Ошибка при выводе очереди: {error}")


@router.message(StateFilter("*"), F.text.in_(EXPORT_USERS_TEXTS))
async def export_users_table(message: Message, state: FSMContext) -> None:
    """Выгружает таблицу users в CSV-файл."""
    if message.from_user is None:
        return
    
    if not is_super_admin(message.from_user.id):
        await message.answer(t("ru", "access_denied"))
        return

    await state.clear()
    
    language_code = await get_user_language(message.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = "ru"
    
    users = await get_all_users()
    
    if not users:
        await message.answer("База пользователей пуста.")
        return
    
    # Создаём CSV в памяти
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["telegram_id", "username", "name", "phone_number", "role", "shop_name", "language_code", "created_at"],
        extrasaction="ignore",
    )
    writer.writeheader()
    for user in users:
        writer.writerow(user)
    
    csv_bytes = output.getvalue().encode("utf-8-sig")  # BOM для Excel
    output.close()
    
    filename = f"users_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    file = BufferedInputFile(csv_bytes, filename=filename)
    
    await message.answer(t(language_code, "users_export_header"))
    await message.answer_document(file)
