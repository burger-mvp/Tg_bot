"""Небольшие обработчики административного меню."""

import csv
import io
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, Message

from database import (
    get_all_users,
    get_queued_posts,
    get_queue_statistics,
    get_user_by_shop_name,
    get_user_language,
    get_user_role,
    set_user_admin,
    set_user_trusted_seller,
)
from keyboards import cancel_keyboard, main_menu
from locales import SUPPORTED_LANGUAGE_CODES, t
from roles import is_super_admin


router = Router(name=__name__)
logger = logging.getLogger(__name__)
SET_TRUSTED_SELLER_TEXTS = frozenset({"🌟 Назначить доверенного продавца", "🌟 Assign trusted seller"})
SET_ADMIN_TEXTS = frozenset({"👤 Назначить администратора", "👤 Assign administrator"})
VIEW_QUEUE_TEXTS = frozenset({"📋 Просмотр очереди", "📋 View queue"})
EXPORT_USERS_TEXTS = frozenset({"📊 Выгрузить users", "📊 Export users"})
SUPER_ADMIN_ACTION_TEXTS = (
    SET_TRUSTED_SELLER_TEXTS | SET_ADMIN_TEXTS | VIEW_QUEUE_TEXTS | EXPORT_USERS_TEXTS
)


class TrustedSellerAssignment(StatesGroup):
    """Ожидание имени магазина для назначения доверенного продавца."""
    
    waiting_for_shop_name = State()


class AdminAssignment(StatesGroup):
    """Ожидание Telegram ID для назначения администратора."""
    
    waiting_for_telegram_id = State()


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
    """Обрабатывает введённое имя магазина и назначает роль доверенного продавца."""
    if message.from_user is None or message.text is None:
        return
    
    if not is_super_admin(message.from_user.id):
        await state.clear()
        await message.answer(t("ru", "access_denied"))
        return
    
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    shop_name = message.text.strip()
    
    telegram_id = await get_user_by_shop_name(shop_name)
    if telegram_id is None:
        await message.answer(t(language_code, "shop_not_found"))
        return
    
    success = await set_user_trusted_seller(telegram_id)
    await state.clear()
    
    if success:
        await message.answer(
            t(language_code, "trusted_seller_assigned"),
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
    """Обрабатывает введённый Telegram ID и назначает роль администратора."""
    if message.from_user is None or message.text is None:
        return
    
    if not is_super_admin(message.from_user.id):
        await state.clear()
        await message.answer(t("ru", "access_denied"))
        return
    
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    
    # Проверяем что введено число
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(t(language_code, "invalid_price"))  # используем похожий текст об ошибке формата
        return
    
    # Проверяем существование пользователя в БД
    user_role = await get_user_role(telegram_id)
    if user_role is None:
        await message.answer(t(language_code, "user_not_found"))
        return
    
    # Назначаем роль admin
    success = await set_user_admin(telegram_id)
    await state.clear()
    
    if success:
        await message.answer(
            t(language_code, "admin_assigned").format(telegram_id=telegram_id),
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
        total = stats.get("total", 0)
        queued = stats.get("queued", 0)
        published = stats.get("published", 0)
        waiting_duplicate = stats.get("waiting_duplicate", 0)

        if not queued_posts and queued == 0:
            await message.answer(t(language_code, "publication_queue_empty"))
            return

        message_text = t(language_code, "queue_status").format(
            total=total,
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
                        scheduled_at=post.scheduled_at.strftime("%d.%m %H:%M"),
                        description=post.description[:80],
                    )
                )
            message_text = f"{message_text}\n\n" + "\n".join(queue_lines)

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
        fieldnames=["telegram_id", "username", "phone_number", "role", "shop_name", "language_code", "created_at"],
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
