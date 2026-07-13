"""Клавиатуры, используемые в обработчиках бота."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

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
    if role == "user":
        buttons = [[KeyboardButton(text=t(language_code, "create_post"))]]
    elif role == "super_admin":
        buttons = [
            [KeyboardButton(text=t(language_code, "admin_panel"))],
            [KeyboardButton(text=t(language_code, "super_admin_panel"))],
        ]
    else:
        buttons = [[KeyboardButton(text=t(language_code, "admin_panel"))]]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def cancel_keyboard(language_code: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру отмены FSM-сценария."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "cancel"), callback_data="post:cancel")]
        ]
    )


def photo_step_keyboard(language_code: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру шага добавления фото."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "skip_photo"), callback_data="post:skip_photo")],
            [InlineKeyboardButton(text=t(language_code, "cancel"), callback_data="post:cancel")],
        ]
    )


def publish_keyboard(language_code: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру подтверждения публикации."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "publish"), callback_data="post:publish")],
            [InlineKeyboardButton(text=t(language_code, "cancel"), callback_data="post:cancel")],
        ]
    )
