"""Административное создание и публикация постов в Telegram-канал."""

import logging
from typing import Final

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import CHANNEL_ID
from database import get_user_language, save_published_post
from keyboards import cancel_keyboard, photo_step_keyboard, publish_keyboard
from locales import SUPPORTED_LANGUAGE_CODES, normalize_language_code, t
from roles import is_admin


router = Router(name=__name__)
logger = logging.getLogger(__name__)

MAX_POST_TEXT_LENGTH: Final = 4096
MAX_PHOTO_CAPTION_LENGTH: Final = 1024
ADMIN_MENU_TEXTS: Final = frozenset(
    {
        "Админ-панель",
        "Панель супер-админа",
        "Admin panel",
        "Super admin panel",
        "لوحة الإدارة",
        "لوحة مدير النظام",
    }
)


class PostCreation(StatesGroup):
    """Шаги создания одного поста администратором."""

    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_confirmation = State()
    publishing = State()


async def _selected_language(telegram_id: int) -> str | None:
    """Возвращает язык из БД, только если он поддерживается."""
    language_code = await get_user_language(telegram_id)
    return language_code if language_code in SUPPORTED_LANGUAGE_CODES else None


async def _require_admin_message(message: Message, state: FSMContext) -> str | None:
    """Проверяет админский доступ в обработчиках текстовых сообщений FSM."""
    if message.from_user is None:
        return None

    data = await state.get_data()
    language_code = normalize_language_code(data.get("language_code"))
    if is_admin(message.from_user.id):
        return language_code

    await state.clear()
    await message.answer(t(language_code, "access_denied"))
    return None


async def _require_admin_callback(callback: CallbackQuery, state: FSMContext) -> str | None:
    """Проверяет админский доступ в callback-обработчиках FSM."""
    data = await state.get_data()
    language_code = normalize_language_code(data.get("language_code"))
    if is_admin(callback.from_user.id):
        return language_code

    await state.clear()
    await callback.answer(t(language_code, "access_denied"), show_alert=True)
    return None


async def _show_preview(message: Message, state: FSMContext, language_code: str) -> None:
    """Показывает предпросмотр поста и кнопку подтверждения публикации."""
    data = await state.get_data()
    text = data["text"]
    photo_id = data.get("photo_id")

    await message.answer(t(language_code, "post_preview"))
    if photo_id:
        if len(text) <= MAX_PHOTO_CAPTION_LENGTH:
            await message.answer_photo(photo_id, caption=text)
        else:
            await message.answer_photo(photo_id)
            await message.answer(text)
            await message.answer(t(language_code, "long_photo_post"))
    else:
        await message.answer(text)

    await message.answer(
        t(language_code, "publish"),
        reply_markup=publish_keyboard(language_code),
    )


@router.message(F.text.in_(ADMIN_MENU_TEXTS))
async def start_post_creation(message: Message, state: FSMContext) -> None:
    """Запускает сценарий создания поста только для администраторов."""
    if message.from_user is None:
        return

    language_code = await _selected_language(message.from_user.id)
    if language_code is None:
        await message.answer(t("ru", "language_required"))
        return
    if not is_admin(message.from_user.id):
        await message.answer(t(language_code, "access_denied"))
        return

    await state.set_state(PostCreation.waiting_for_text)
    await state.update_data(language_code=language_code)
    await message.answer(
        t(language_code, "enter_post_text"),
        reply_markup=cancel_keyboard(language_code),
    )


@router.message(PostCreation.waiting_for_text, F.text)
async def receive_post_text(message: Message, state: FSMContext) -> None:
    """Сохраняет текст будущего поста и переходит к добавлению фото."""
    language_code = await _require_admin_message(message, state)
    if language_code is None or message.text is None:
        return

    text = message.text.strip()
    if not text:
        await message.answer(t(language_code, "text_empty"), reply_markup=cancel_keyboard(language_code))
        return
    if len(text) > MAX_POST_TEXT_LENGTH:
        await message.answer(
            t(language_code, "text_too_long", max_length=MAX_POST_TEXT_LENGTH),
            reply_markup=cancel_keyboard(language_code),
        )
        return

    await state.update_data(text=text)
    await state.set_state(PostCreation.waiting_for_photo)
    await message.answer(
        t(language_code, "send_one_photo"),
        reply_markup=photo_step_keyboard(language_code),
    )


@router.message(PostCreation.waiting_for_text)
async def reject_non_text(message: Message, state: FSMContext) -> None:
    """Не позволяет передать вложение вместо текста поста."""
    language_code = await _require_admin_message(message, state)
    if language_code is not None:
        await message.answer(t(language_code, "send_text_only"), reply_markup=cancel_keyboard(language_code))


@router.message(PostCreation.waiting_for_photo, F.photo)
async def receive_post_photo(message: Message, state: FSMContext) -> None:
    """Сохраняет file_id единственного присланного фото и показывает предпросмотр."""
    language_code = await _require_admin_message(message, state)
    if language_code is None or not message.photo:
        return

    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(PostCreation.waiting_for_confirmation)
    await _show_preview(message, state, language_code)


@router.message(PostCreation.waiting_for_photo)
async def reject_non_photo(message: Message, state: FSMContext) -> None:
    """Подсказывает допустимые действия на шаге добавления фото."""
    language_code = await _require_admin_message(message, state)
    if language_code is not None:
        await message.answer(t(language_code, "send_photo_only"), reply_markup=photo_step_keyboard(language_code))


@router.callback_query(PostCreation.waiting_for_photo, F.data == "post:skip_photo")
async def skip_post_photo(callback: CallbackQuery, state: FSMContext) -> None:
    """Переходит к предпросмотру поста без фото."""
    language_code = await _require_admin_callback(callback, state)
    if language_code is None or callback.message is None:
        return

    await callback.answer()
    await state.set_state(PostCreation.waiting_for_confirmation)
    await _show_preview(callback.message, state, language_code)


@router.callback_query(F.data == "post:cancel")
async def cancel_post_creation(callback: CallbackQuery, state: FSMContext) -> None:
    """Сбрасывает сценарий создания поста на любом шаге."""
    current_state = await state.get_state()
    if current_state is None:
        await callback.answer()
        return

    language_code = await _require_admin_callback(callback, state)
    if language_code is None:
        return

    await state.clear()
    await callback.answer(t(language_code, "post_cancelled"))
    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
        await callback.message.answer(t(language_code, "post_cancelled"))


@router.callback_query(PostCreation.waiting_for_confirmation, F.data == "post:publish")
async def publish_post(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Публикует подтвержденный пост в канал и сохраняет его в PostgreSQL."""
    language_code = await _require_admin_callback(callback, state)
    if language_code is None or callback.message is None:
        return

    data = await state.get_data()
    text = data.get("text")
    photo_id = data.get("photo_id")
    if not isinstance(text, str):
        await state.clear()
        await callback.answer(t(language_code, "post_cancelled"), show_alert=True)
        return

    await state.set_state(PostCreation.publishing)
    await callback.answer(t(language_code, "publishing"))
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    try:
        if photo_id:
            if len(text) <= MAX_PHOTO_CAPTION_LENGTH:
                await bot.send_photo(CHANNEL_ID, photo_id, caption=text)
            else:
                await bot.send_photo(CHANNEL_ID, photo_id)
                await bot.send_message(CHANNEL_ID, text)
        else:
            await bot.send_message(CHANNEL_ID, text)
    except TelegramAPIError as error:
        logger.exception("Не удалось опубликовать пост в канал %s: %s", CHANNEL_ID, error)
        await state.set_state(PostCreation.waiting_for_confirmation)
        await callback.message.answer(
            t(language_code, "post_publish_failed"),
            reply_markup=publish_keyboard(language_code),
        )
        return

    try:
        await save_published_post(text, photo_id)
    except Exception:
        # Сообщение уже опубликовано в Telegram, поэтому повторную отправку не делаем.
        logger.exception("Пост опубликован, но не сохранен в таблице posts.")

    await state.clear()
    await callback.message.answer(t(language_code, "post_published"))


@router.callback_query(PostCreation.publishing, F.data == "post:publish")
async def reject_duplicate_publish(callback: CallbackQuery, state: FSMContext) -> None:
    """Защищает от двойного нажатия кнопки публикации."""
    language_code = normalize_language_code((await state.get_data()).get("language_code"))
    await callback.answer(t(language_code, "publish_in_progress"), show_alert=True)
