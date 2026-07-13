"""Клавиатуры, используемые в обработчиках бота."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from locales import t


LANGUAGE_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="language:ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="language:en")],
        [InlineKeyboardButton(text="🇸🇦 العربية", callback_data="language:ar")],
    ]
)


def main_menu(role: str, language_code: str) -> ReplyKeyboardMarkup:
    """Создает главное Reply-меню с учетом языка и роли пользователя."""
    buttons = [[KeyboardButton(text=t(language_code, "create_post"))]]
    if role != "user":
        buttons.append([KeyboardButton(text=t(language_code, "admin_panel"))])
    if role == "super_admin":
        buttons.append([KeyboardButton(text=t(language_code, "super_admin_panel"))])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def phone_keyboard(language_code: str) -> ReplyKeyboardMarkup:
    """Создает Reply-кнопку для безопасной передачи контакта самого пользователя."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(language_code, "share_phone"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def cancel_keyboard(language_code: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру отмены FSM-сценария."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "cancel"), callback_data="post:cancel")]
        ]
    )


def media_step_keyboard(language_code: str) -> InlineKeyboardMarkup:
    """Создает кнопки завершения загрузки видео и отмены сценария."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "media_uploaded"), callback_data="post:media_done")],
            [InlineKeyboardButton(text=t(language_code, "cancel"), callback_data="post:cancel")],
        ]
    )


def category_keyboard(language_code: str) -> InlineKeyboardMarkup:
    """Создает выбор категории товара."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "engine"), callback_data="post:category:engine")],
            [InlineKeyboardButton(text=t(language_code, "body"), callback_data="post:category:body")],
            [InlineKeyboardButton(text=t(language_code, "cancel"), callback_data="post:cancel")],
        ]
    )


def engine_type_keyboard(language_code: str) -> InlineKeyboardMarkup:
    """Создает выбор комплектации двигателя."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "engine_only"), callback_data="post:engine:only")],
            [
                InlineKeyboardButton(
                    text=t(language_code, "engine_with_transmission"),
                    callback_data="post:engine:transmission",
                )
            ],
            [InlineKeyboardButton(text=t(language_code, "cancel"), callback_data="post:cancel")],
        ]
    )


def moderation_keyboard(post_id: str, language_code: str) -> InlineKeyboardMarkup:
    """Создает кнопки одобрения и правки поста для супер-администратора."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "approve"), callback_data=f"moderation:approve:{post_id}")],
            [InlineKeyboardButton(text=t(language_code, "edit"), callback_data=f"moderation:edit:{post_id}")],
        ]
    )
