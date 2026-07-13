"""Регистрация пользователей и стартовые ролевые меню."""

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from config import ADMIN_IDS, SUPER_ADMIN_ID
from database import add_user, get_user_role, user_exists


router = Router(name=__name__)
logger = logging.getLogger(__name__)

CREATE_POST_TEXT = "Создать пост"
ADMIN_PANEL_TEXT = "Админ-панель"
SUPER_ADMIN_PANEL_TEXT = "Панель супер-админа"


class Registration(StatesGroup):
    """Состояния первого этапа регистрации пользователя."""

    waiting_for_phone = State()


def get_role(telegram_id: int) -> str:
    """Вычисляет первоначальную роль по настройкам проекта."""
    if telegram_id == SUPER_ADMIN_ID:
        return "super_admin"
    if telegram_id in ADMIN_IDS:
        return "admin"
    return "user"


def user_menu() -> ReplyKeyboardMarkup:
    """Создает меню для обычного пользователя."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CREATE_POST_TEXT)]],
        resize_keyboard=True,
    )


def admin_menu(role: str) -> ReplyKeyboardMarkup:
    """Создает временное меню администратора с учетом его роли."""
    buttons = [[KeyboardButton(text=ADMIN_PANEL_TEXT)]]
    if role == "super_admin":
        buttons.append([KeyboardButton(text=SUPER_ADMIN_PANEL_TEXT)])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


async def show_welcome(message: Message, role: str) -> None:
    """Отправляет приветствие и соответствующее роли Reply-меню."""
    if role == "user":
        await message.answer(
            "Добро пожаловать! Выберите действие в меню ниже.",
            reply_markup=user_menu(),
        )
        return

    role_title = "супер-администратор" if role == "super_admin" else "администратор"
    await message.answer(
        f"С возвращением! Вы вошли как {role_title}.",
        reply_markup=admin_menu(role),
    )


async def notify_admins(bot: Bot, telegram_id: int, phone_number: str) -> None:
    """Уведомляет всех настроенных администраторов о новой регистрации."""
    # dict.fromkeys сохраняет порядок и исключает повторную отправку, если ID совпадают.
    recipient_ids = list(dict.fromkeys([SUPER_ADMIN_ID, *ADMIN_IDS]))
    notification = (
        "Зарегистрирован новый пользователь! "
        f"ID: {telegram_id}, Номер: {phone_number}"
    )

    for admin_id in recipient_ids:
        try:
            await bot.send_message(admin_id, notification)
        except (TelegramForbiddenError, TelegramBadRequest) as error:
            # Бот не может написать пользователю, пока тот не начал с ним диалог.
            logger.warning("Не удалось отправить уведомление админу %s: %s", admin_id, error)


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    """Запускает регистрацию или отображает меню уже зарегистрированному пользователю."""
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    if await user_exists(telegram_id):
        await state.clear()
        role = await get_user_role(telegram_id)
        # Защита от некорректных старых данных в базе.
        await show_welcome(message, role if role in {"user", "admin", "super_admin"} else "user")
        return

    await state.set_state(Registration.waiting_for_phone)
    await message.answer("Здравствуйте! Введите ваш номер телефона обычным текстовым сообщением.")


@router.message(Registration.waiting_for_phone, F.text)
async def save_phone_number(message: Message, state: FSMContext, bot: Bot) -> None:
    """Сохраняет телефон, назначает роль и уведомляет администраторов."""
    if message.from_user is None or message.text is None:
        return

    phone_number = message.text.strip()
    if not phone_number:
        await message.answer("Номер телефона не должен быть пустым. Введите его еще раз.")
        return

    telegram_id = message.from_user.id
    role = get_role(telegram_id)
    await add_user(telegram_id, phone_number, role)
    await state.clear()

    await message.answer("Регистрация завершена.")
    await notify_admins(bot, telegram_id, phone_number)
    await show_welcome(message, role)


@router.message(F.text == CREATE_POST_TEXT)
async def create_post_placeholder(message: Message) -> None:
    """Временный обработчик будущего сценария создания поста."""
    await message.answer("Создание поста будет добавлено в следующей части разработки.")


@router.message(F.text.in_({ADMIN_PANEL_TEXT, SUPER_ADMIN_PANEL_TEXT}))
async def admin_panel_placeholder(message: Message) -> None:
    """Временный обработчик административного меню."""
    await message.answer("Раздел администратора пока находится в разработке.")
