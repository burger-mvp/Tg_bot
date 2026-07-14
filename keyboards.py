"""Клавиатуры, используемые в обработчиках бота."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from locales import t


LANGUAGE_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="language:ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="language:en")],
        [InlineKeyboardButton(text="🇸🇦 العربية", callback_data="language:ar")],
        [InlineKeyboardButton(text="🇦🇫 دری", callback_data="language:fa")],
        [InlineKeyboardButton(text="🇵🇰 اردو", callback_data="language:ur")],
        [InlineKeyboardButton(text="🇮🇳 हिन्दी", callback_data="language:hi")],
        [InlineKeyboardButton(text="🇧🇩 বাংলা", callback_data="language:bn")],
    ]
)


def main_menu(role: str, language_code: str) -> ReplyKeyboardMarkup:
    """Создает главное Reply-меню с учетом языка и роли пользователя."""
    buttons = [[KeyboardButton(text=t(language_code, "create_post"))]]
    if role != "user" and role != "trusted_seller":
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


def media_step_keyboard(language_code: str) -> ReplyKeyboardMarkup:
    """Создает Reply-клавиатуру с кнопкой завершения загрузки медиа внизу экрана."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(language_code, "media_uploaded"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
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
    """Создает кнопки одобрения, правки и отклонения поста для супер-администратора."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "approve"), callback_data=f"moderation:approve:{post_id}")],
            [InlineKeyboardButton(text=t(language_code, "edit"), callback_data=f"moderation:edit:{post_id}")],
            [InlineKeyboardButton(text=t(language_code, "reject"), callback_data=f"moderation:reject:{post_id}")],
        ]
    )


def super_admin_menu_keyboard(language_code: str) -> InlineKeyboardMarkup:
    """Создает дополнительное меню супер-администратора."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(language_code, "set_trusted_seller"), callback_data="super_admin:set_trusted")],
            [InlineKeyboardButton(text=t(language_code, "set_admin"), callback_data="super_admin:set_admin")],
            [InlineKeyboardButton(text=t(language_code, "view_queue"), callback_data="super_admin:view_queue")],
            [InlineKeyboardButton(text=t(language_code, "export_users"), callback_data="super_admin:export_users")],
        ]
    )
