"""Небольшие обработчики административного меню."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database import get_user_by_shop_name, get_user_language, get_user_role, set_user_admin, set_user_trusted_seller
from keyboards import cancel_keyboard, main_menu, super_admin_menu_keyboard
from locales import SUPPORTED_LANGUAGE_CODES, t
from roles import get_role_from_db_or_config, is_admin, is_super_admin


router = Router(name=__name__)
ADMIN_MENU_TEXTS = frozenset({"Админ-панель", "Admin panel", "لوحة الإدارة"})
SUPER_ADMIN_MENU_TEXTS = frozenset({"Супер админ панель", "Super admin panel", "لوحة المدير العام"})


class TrustedSellerAssignment(StatesGroup):
    """Ожидание имени магазина для назначения доверенного продавца."""
    
    waiting_for_shop_name = State()


class AdminAssignment(StatesGroup):
    """Ожидание Telegram ID для назначения администратора."""
    
    waiting_for_telegram_id = State()


@router.message(F.text.in_(ADMIN_MENU_TEXTS))
async def open_admin_panel(message: Message) -> None:
    """Подтверждает доступ к панели; создание постов доступно общей кнопкой."""
    if message.from_user is None:
        return

    language_code = await get_user_language(message.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        await message.answer(t("ru", "language_required"))
        return
    if not is_admin(message.from_user.id):
        await message.answer(t(language_code, "access_denied"))
        return
    
    role = await get_role_from_db_or_config(message.from_user.id)
    await message.answer(
        t(language_code, "admin_panel_hint"),
        reply_markup=main_menu(role, language_code),
    )


@router.message(F.text.in_(SUPER_ADMIN_MENU_TEXTS))
async def open_super_admin_panel(message: Message) -> None:
    """Показывает супер-администратору актуальное меню и сценарий модерации."""
    if message.from_user is None:
        return

    language_code = await get_user_language(message.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        await message.answer(t("ru", "language_required"))
        return
    if not is_super_admin(message.from_user.id):
        await message.answer(t(language_code, "access_denied"))
        return
    await message.answer(
        t(language_code, "super_admin_panel_hint"),
        reply_markup=super_admin_menu_keyboard(language_code),
    )


@router.callback_query(F.data == "super_admin:set_trusted")
async def start_trusted_seller_assignment(callback_query: Message, state: FSMContext) -> None:
    """Начинает процесс назначения доверенного продавца."""
    if callback_query.from_user is None:
        return
    
    if not is_super_admin(callback_query.from_user.id):
        await callback_query.answer(t("ru", "access_denied"), show_alert=True)
        return
    
    language_code = await get_user_language(callback_query.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = "ru"
    
    await state.clear()
    await state.set_state(TrustedSellerAssignment.waiting_for_shop_name)
    await state.update_data(language_code=language_code)
    
    if callback_query.message is not None:
        await callback_query.answer()
        await callback_query.message.answer(
            t(language_code, "enter_shop_name_for_trust"),
            reply_markup=cancel_keyboard(language_code),
        )


@router.message(TrustedSellerAssignment.waiting_for_shop_name, F.text)
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


@router.message(TrustedSellerAssignment.waiting_for_shop_name)
async def reject_non_text_shop_name(message: Message, state: FSMContext) -> None:
    """Отклоняет нетекстовый ввод при назначении доверенного продавца."""
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    await message.answer(t(language_code, "enter_shop_name_for_trust"))


@router.callback_query(F.data == "super_admin:set_admin")
async def start_admin_assignment(callback_query: Message, state: FSMContext) -> None:
    """Начинает процесс назначения администратора."""
    if callback_query.from_user is None:
        return
    
    if not is_super_admin(callback_query.from_user.id):
        await callback_query.answer(t("ru", "access_denied"), show_alert=True)
        return
    
    language_code = await get_user_language(callback_query.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = "ru"
    
    await state.clear()
    await state.set_state(AdminAssignment.waiting_for_telegram_id)
    await state.update_data(language_code=language_code)
    
    if callback_query.message is not None:
        await callback_query.answer()
        await callback_query.message.answer(
            t(language_code, "enter_telegram_id_for_admin"),
            reply_markup=cancel_keyboard(language_code),
        )


@router.message(AdminAssignment.waiting_for_telegram_id, F.text)
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


@router.message(AdminAssignment.waiting_for_telegram_id)
async def reject_non_text_telegram_id(message: Message, state: FSMContext) -> None:
    """Отклоняет нетекстовый ввод при назначении администратора."""
    data = await state.get_data()
    language_code = data.get("language_code", "ru")
    await message.answer(t(language_code, "enter_telegram_id_for_admin"))
