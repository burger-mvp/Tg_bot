"""Точка входа Telegram-бота."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError

from config import TOKEN
from database import close_db, init_db
from handlers.admin import router as admin_router
from handlers.posts import router as posts_router
from handlers.start import router as start_router
from middlewares.role import RoleMiddleware
from scheduler.post_scheduler import PostScheduler


NETWORK_RETRY_DELAY_SECONDS = 5


async def main() -> None:
    """Инициализирует зависимости и запускает long polling."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    bot = Bot(token=TOKEN)
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(RoleMiddleware())
    dispatcher.include_router(start_router)
    dispatcher.include_router(admin_router)
    dispatcher.include_router(posts_router)

    await init_db()
    post_scheduler = PostScheduler(bot)
    await post_scheduler.start()
    try:
        while True:
            try:
                await dispatcher.start_polling(bot)
                break
            except TelegramNetworkError as error:
                # Временный сбой сети (например, недоступность api.telegram.org)
                # не должен требовать ручного перезапуска бота.
                logging.warning(
                    "Не удалось подключиться к Telegram API: %s. Повтор через %s сек.",
                    error,
                    NETWORK_RETRY_DELAY_SECONDS,
                )
                await asyncio.sleep(NETWORK_RETRY_DELAY_SECONDS)
    finally:
        post_scheduler.shutdown()
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
