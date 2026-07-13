"""Выбор языка, регистрация и главное меню."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import (
    get_user_language,
    get_user_phone_number,
    update_user_phone_number,
    update_user_role,
    upsert_user,
)
from keyboards import LANGUAGE_KEYBOARD, main_menu
from locales import SUPPORTED_LANGUAGE_CODES, t
from roles import get_role


router = Router(name=__name__)
MAX_PHONE_NUMBER_LENGTH = 64


class Registration(StatesGroup):
    """Шаги регистрации: после выбора языка ожидается номер телефона."""

    waiting_for_phone = State()


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


async def request_phone_number(message: Message, state: FSMContext, language_code: str) -> None:
    """Переводит пользователя на шаг ввода номера телефона."""
    await state.set_state(Registration.waiting_for_phone)
    await state.update_data(language_code=language_code)
    await message.answer(t(language_code, "enter_phone"))


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    """Запускает регистрацию: язык, номер телефона, затем главное меню."""
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
    if not await get_user_phone_number(telegram_id):
        await request_phone_number(message, state, language_code)
        return

    await show_welcome(message, role, language_code)


@router.callback_query(F.data.startswith("language:"))
async def select_language(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет язык и переводит нового пользователя к вводу номера."""
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
    if not await get_user_phone_number(telegram_id):
        await request_phone_number(callback.message, state, language_code)
        return

    await show_welcome(callback.message, role, language_code)


@router.message(Registration.waiting_for_phone, F.text)
async def save_phone_number(message: Message, state: FSMContext) -> None:
    """Сохраняет номер телефона и завершает регистрацию пользователя."""
    if message.from_user is None or message.text is None:
        return

    language_code = (await state.get_data()).get("language_code")
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = await get_user_language(message.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        await state.clear()
        await message.answer(t("ru", "choose_language"), reply_markup=LANGUAGE_KEYBOARD)
        return

    phone_number = message.text.strip()
    if not phone_number:
        await message.answer(t(language_code, "phone_empty"))
        return
    if len(phone_number) > MAX_PHONE_NUMBER_LENGTH:
        await message.answer(
            t(language_code, "phone_too_long", max_length=MAX_PHONE_NUMBER_LENGTH)
        )
        return

    role = get_role(message.from_user.id)
    await update_user_role(message.from_user.id, role)
    await update_user_phone_number(message.from_user.id, phone_number)
    await state.clear()

    await message.answer(t(language_code, "registration_complete"))
    await show_welcome(message, role, language_code)


@router.message(Registration.waiting_for_phone)
async def reject_non_text_phone(message: Message, state: FSMContext) -> None:
    """Не принимает вложения вместо номера телефона."""
    language_code = (await state.get_data()).get("language_code")
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = "ru"
    await message.answer(t(language_code, "send_phone_only"))


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
