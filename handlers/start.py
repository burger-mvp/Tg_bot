"""Регистрация пользователя: язык, контакт и главное меню."""

import logging
from typing import Final

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from database import (
    assign_shop_name_on_registration,
    display_name,
    get_user_language,
    get_user_phone_number,
    save_phone_number_and_mark_registered,
    update_user_role,
    update_user_username,
    upsert_user,
)
from keyboards import LANGUAGE_KEYBOARD, main_menu, phone_keyboard, start_keyboard
from locales import SUPPORTED_LANGUAGE_CODES, t
from roles import get_role_from_db_or_config, notification_recipient_ids
from utils.premium_emoji import strip_tg_emoji_tags, tg_emoji_html_to_entities


router = Router(name=__name__)
logger = logging.getLogger(__name__)
MAX_PHONE_NUMBER_LENGTH: Final = 64
START_REGISTRATION_TEXTS: Final = frozenset({
    "🚀 Начать", "🚀 Start",
})


class Registration(StatesGroup):
    """Единственный обязательный шаг после выбора языка."""

    waiting_for_phone = State()


async def show_welcome(message: Message, role: str, language_code: str) -> None:
    """Отправляет приветствие и главное Reply-меню для роли пользователя."""
    greeting_key = {
        "user": "welcome_user",
        "admin": "welcome_admin",
        "super_admin": "welcome_super_admin",
        "trusted_seller": "welcome_trusted_seller",
    }.get(role, "welcome_user")
    await message.answer(
        t(language_code, greeting_key),
        reply_markup=main_menu(role, language_code),
    )


async def request_phone_number(message: Message, state: FSMContext, language_code: str) -> None:
    """Запрашивает контакт через Telegram-кнопку, а не произвольный текст."""
    await state.set_state(Registration.waiting_for_phone)
    await state.update_data(language_code=language_code)
    await message.answer(t(language_code, "enter_phone"), reply_markup=phone_keyboard(language_code))


async def _notify_registration(bot: Bot, telegram_id: int, phone_number: str) -> None:
    """Уведомляет всех ответственных о первой завершенной регистрации."""
    notification = f"Зарегистрирован новый пользователь! ID: {telegram_id}, Номер телефона: {phone_number}"
    for recipient_id in notification_recipient_ids():
        try:
            await bot.send_message(recipient_id, notification)
        except TelegramAPIError:
            # Бот не может написать пользователю, который ни разу не открывал с ним чат.
            logger.warning("Не удалось отправить уведомление о регистрации пользователю %s", recipient_id)


async def _begin_registration(message: Message, state: FSMContext) -> None:
    """Открывает выбор языка для нового или удаленного из БД пользователя."""
    await state.clear()
    await message.answer(
        t("ru", "start_prompt"),
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(t("ru", "choose_language"), reply_markup=LANGUAGE_KEYBOARD)


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    """Запускает регистрацию или открывает главное меню зарегистрированного пользователя."""
    if message.from_user is None:
        return

    await state.clear()
    telegram_id = message.from_user.id
    language_code = await get_user_language(telegram_id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        await message.answer(t("ru", "start_prompt"), reply_markup=start_keyboard())
        return

    # Проверяем, есть ли телефон (зарегистрирован ли пользователь)
    if not await get_user_phone_number(telegram_id):
        # Пользователь не завершил регистрацию, запрашиваем контакт
        await request_phone_number(message, state, language_code)
        return

    # Пользователь уже зарегистрирован, обновляем роль и показываем меню
    role = await get_role_from_db_or_config(telegram_id)
    await update_user_role(telegram_id, role)
    await update_user_username(telegram_id, message.from_user.username)
    await show_welcome(message, role, language_code)


@router.message(F.text.in_(START_REGISTRATION_TEXTS))
async def start_registration_from_button(message: Message, state: FSMContext) -> None:
    """Запускает тот же сценарий регистрации по Reply-кнопке «Начать»."""
    if message.from_user is None:
        return
    if await get_user_language(message.from_user.id) in SUPPORTED_LANGUAGE_CODES:
        await command_start(message, state)
        return
    await _begin_registration(message, state)


@router.callback_query(F.data.startswith("language:"))
async def select_language(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняет язык и переводит пользователя на шаг передачи контакта."""
    if callback.message is None or callback.data is None:
        return

    language_code = callback.data.removeprefix("language:")
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        await callback.answer()
        return

    await state.clear()
    telegram_id = callback.from_user.id
    role = await get_role_from_db_or_config(telegram_id)
    await upsert_user(
        telegram_id,
        role,
        language_code,
        callback.from_user.username,
        display_name(callback.from_user.username, callback.from_user.first_name, callback.from_user.last_name),
    )

    await callback.answer(t(language_code, "language_saved"))
    await callback.message.edit_reply_markup(reply_markup=None)
    if not await get_user_phone_number(telegram_id):
        await request_phone_number(callback.message, state, language_code)
        return

    await show_welcome(callback.message, role, language_code)


@router.message(Registration.waiting_for_phone, F.contact)
async def save_phone_number(message: Message, state: FSMContext, bot: Bot) -> None:
    """Принимает только собственный Telegram-контакт и завершает регистрацию."""
    if message.from_user is None or message.contact is None:
        return

    language_code = (await state.get_data()).get("language_code")
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = await get_user_language(message.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        await state.clear()
        await message.answer(t("ru", "choose_language"), reply_markup=LANGUAGE_KEYBOARD)
        return

    if message.contact.user_id != message.from_user.id:
        await message.answer(t(language_code, "foreign_contact"), reply_markup=phone_keyboard(language_code))
        return

    phone_number = message.contact.phone_number.strip()
    if not phone_number or len(phone_number) > MAX_PHONE_NUMBER_LENGTH:
        await message.answer(t(language_code, "send_contact_only"), reply_markup=phone_keyboard(language_code))
        return

    role = await get_role_from_db_or_config(message.from_user.id)
    is_new_registration = await save_phone_number_and_mark_registered(
        message.from_user.id,
        phone_number,
        role,
    )
    
    # Присваиваем shop_name при первой регистрации
    if is_new_registration:
        await assign_shop_name_on_registration(message.from_user.id)
    
    await state.clear()

    await message.answer(t(language_code, "registration_complete"))
    await show_welcome(message, role, language_code)
    if is_new_registration:
        await _notify_registration(bot, message.from_user.id, phone_number)


@router.message(Registration.waiting_for_phone)
async def reject_non_contact_phone(message: Message, state: FSMContext) -> None:
    """Подсказывает корректный способ передачи номера телефона."""
    language_code = (await state.get_data()).get("language_code")
    await message.answer(t(language_code, "send_contact_only"), reply_markup=phone_keyboard(language_code))


@router.message(Command("info"))
async def command_info(message: Message) -> None:
    """Отображает информацию о боте на языке пользователя."""
    if message.from_user is None:
        return
    
    language_code = await get_user_language(message.from_user.id)
    if language_code not in SUPPORTED_LANGUAGE_CODES:
        language_code = "ru"

    info_text = t(language_code, "info_message")
    plain_info_text, entities = tg_emoji_html_to_entities(info_text)
    try:
        await message.answer(plain_info_text, entities=entities)
    except TelegramAPIError:
        logger.warning("Не удалось отправить /info с Telegram premium emoji", exc_info=True)
        await message.answer(strip_tg_emoji_tags(info_text))
