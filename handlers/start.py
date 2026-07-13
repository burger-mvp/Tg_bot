"""Выбор языка, регистрация и главное меню."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import get_user_language, update_user_role, upsert_user
from keyboards import LANGUAGE_KEYBOARD, main_menu
from locales import SUPPORTED_LANGUAGE_CODES, t
from roles import get_role


router = Router(name=__name__)


async def show_welcome(message: Message, role: str, language_code: str) -> None:
    """Отправляет приветствие и соответствующее роли Reply-меню."""
    if role == "user":
        await message.answer(
            t(language_code, "welcome_user"),
            reply_markup=main_menu(role, language_code),
        )
        return

    greeting_key = "welcome_super_admin" if role == "super_admin" else "welcome_admin"
    await message.answer(
        t(language_code, greeting_key),
        reply_markup=main_menu(role, language_code),
    )


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    """Запрашивает язык или отображает локализованное главное меню."""
    if message.from_user is None:
        return

    await state.clear()
    telegram_id = message.from_user.id
    language_code = await get_user_language(telegram_id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        await message.answer(t("ru", "choose_language"), reply_markup=LANGUAGE_KEYBOARD)
        return

    role = get_role(telegram_id)
    await update_user_role(telegram_id, role)
    await show_welcome(message, role, language_code)


@router.callback_query(F.data.startswith("language:"))
async def select_language(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет язык пользователя и завершает регистрацию."""
    if callback.from_user is None or callback.message is None or callback.data is None:
        return

    language_code = callback.data.removeprefix("language:")
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        await callback.answer()
        return

    await state.clear()
    telegram_id = callback.from_user.id
    role = get_role(telegram_id)
    await upsert_user(telegram_id, role, language_code)

    await callback.answer(t(language_code, "language_saved"))
    await callback.message.edit_reply_markup(reply_markup=None)
    await show_welcome(callback.message, role, language_code)


@router.message(F.text.in_({"Создать пост", "Create post", "إنشاء منشور"}))
async def create_post_placeholder(message: Message) -> None:
    """Отвечает на пока не реализованное создание поста обычным пользователем."""
    if message.from_user is None:
        return

    language_code = await get_user_language(message.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        await message.answer(t("ru", "language_required"))
        return

    await message.answer(t(language_code, "feature_in_development"))
