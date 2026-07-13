"""Небольшие обработчики административного меню."""

from aiogram import F, Router
from aiogram.types import Message

from database import get_user_language
from locales import SUPPORTED_LANGUAGE_CODES, t
from roles import is_admin


router = Router(name=__name__)
ADMIN_MENU_TEXTS = frozenset({"Админ-панель", "Admin panel", "لوحة الإدارة"})


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
    await message.answer(t(language_code, "admin_panel_hint"))
