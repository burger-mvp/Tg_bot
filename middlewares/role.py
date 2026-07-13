"""Вычисление текущей роли пользователя до обработки обновления."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

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
        return await handler(event, data)
