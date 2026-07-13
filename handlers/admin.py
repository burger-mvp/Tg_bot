"""Небольшие обработчики административного меню."""

from aiogram import F, Router
from aiogram.types import Message

from database import get_user_language
from keyboards import main_menu
from locales import SUPPORTED_LANGUAGE_CODES, t
from roles import get_role, is_admin, is_super_admin


router = Router(name=__name__)
ADMIN_MENU_TEXTS = frozenset({"Админ-панель", "Admin panel", "لوحة الإدارة"})
SUPER_ADMIN_MENU_TEXTS = frozenset({"Супер админ панель", "Super admin panel", "لوحة المدير العام"})


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
    await message.answer(
        t(language_code, "admin_panel_hint"),
        reply_markup=main_menu(get_role(message.from_user.id), language_code),
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
        reply_markup=main_menu("super_admin", language_code),
    )
