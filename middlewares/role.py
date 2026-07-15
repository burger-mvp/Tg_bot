"""Вычисление текущей роли пользователя до обработки обновления."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from database import display_name, update_user_profile
from roles import get_role


class RoleMiddleware(BaseMiddleware):
    """Добавляет актуальную роль из переменных окружения в данные обработчика."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if isinstance(user, User):
            data["role"] = get_role(user.id)
            await update_user_profile(
                user.id,
                user.username,
                display_name(user.username, user.first_name, user.last_name),
            )
        return await handler(event, data)
