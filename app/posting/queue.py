import asyncio
import logging
from typing import List

from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.db.models import User
from app.posting.errors import deactivate_user

# Настройки скорости
BATCH_SIZE = 25  # Отправляем пачками по 25 штук
RATE_LIMIT = 1.1  # Пауза между пачками (сек) -> ~22 RPS (безопасно)

logger = logging.getLogger(__name__)


async def start_broadcast(
        bot: Bot,
        session_maker: async_sessionmaker,
        from_chat_id: int,
        message_id: int,
) -> int:
    """
    Запускает рассылку поста по всем активным пользователям.
    Возвращает количество успешно отправленных сообщений.
    """
    success_count = 0

    async with session_maker() as session:
        # 1. Считаем общее кол-во (для логов)
        # (Опционально, можно убрать для скорости)
        # total_users = await session.scalar(select(func.count(User.id)).where(User.is_active == True))
        # logger.info(f"Начинаем рассылку поста {message_id} для {total_users} пользователей")

        # 2. Итерируемся по пользователям пачками (Stream/Pagination)
        # Используем stream() чтобы не грузить 10к юзеров в память сразу
        stmt = select(User.telegram_id).where(User.is_active == True).execution_options(yield_per=100)

        result = await session.stream(stmt)

        batch = []

        async for row in result:
            user_tg_id = row[0]
            batch.append(user_tg_id)

            if len(batch) >= BATCH_SIZE:
                success = await _send_batch(bot, batch, from_chat_id, message_id)
                success_count += success
                batch.clear()
                await asyncio.sleep(RATE_LIMIT)  # Держим рейт-лимит

        # Отправляем остатки
        if batch:
            success = await _send_batch(bot, batch, from_chat_id, message_id)
            success_count += success

    logger.info(f"🏁 Рассылка завершена. Успешно: {success_count}")
    return success_count


async def _send_batch(
        bot: Bot,
        user_ids: List[int],
        from_chat_id: int,
        message_id: int
) -> int:
    """
    Отправляет пачку сообщений параллельно
    """
    tasks = []
    for tg_id in user_ids:
        tasks.append(_safe_send(bot, tg_id, from_chat_id, message_id))

    # Запускаем 25 запросов ОДНОВРЕМЕННО
    results = await asyncio.gather(*tasks)
    return sum(results)


async def _safe_send(
        bot: Bot,
        telegram_id: int,
        from_chat_id: int,
        message_id: int,
) -> int:
    """
    Отправка одному юзеру с обработкой ошибок.
    Возвращает 1 при успехе, 0 при ошибке.
    """
    try:
        # Используем copy_message для чистого вида (без "forwarded from")
        await bot.copy_message(
            chat_id=telegram_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
        )
        return 1

    except TelegramRetryAfter as e:
        # Если словили лимит - ждем и пробуем один раз (рекурсия)
        logger.warning(f"FloodWait {e.retry_after}s for {telegram_id}")
        await asyncio.sleep(e.retry_after)
        return await _safe_send(bot, telegram_id, from_chat_id, message_id)

    except (TelegramForbiddenError, TelegramBadRequest):
        # Юзер заблочил бота -> деактивируем
        # ВАЖНО: Тут мы не передаем сессию, поэтому deactivate_user должен
        # уметь создавать свою сессию или мы должны прокидывать её.
        # Для скорости - просто логируем, а чистку базы делаем отдельным скриптом раз в сутки.
        await deactivate_user(telegram_id)
        return 0

    except Exception as e:
        logger.error(f"Error sending to {telegram_id}: {e}")
        return 0



















# import asyncio
# from aiogram import Bot
# from aiogram.types import Message
# from asyncio import Queue
# from aiogram.exceptions import (
#     TelegramForbiddenError,
#     TelegramBadRequest,
#     TelegramRetryAfter,
# )
#
# from app.posting.errors import deactivate_user
#
#
# SEND_RATE = 25
# SEND_DELAY = 1 / SEND_RATE
#
# _send_queue: Queue[tuple[int, Message]] = Queue()
#
#
#
# # Основной sender
# async def start_sender(bot: Bot) -> None:
#     while True:
#         telegram_id, message = await _send_queue.get()
#
#         try:
#             await _safe_send(bot, telegram_id, message)
#
#         except TelegramRetryAfter as e:
#             await asyncio.sleep(e.retry_after)
#             await _send_queue.put((telegram_id, message))
#
#         except (TelegramForbiddenError, TelegramBadRequest):
#             await deactivate_user(telegram_id)
#
#         except Exception:
#             # логирование добавишь позже
#             pass
#
#         finally:
#             await asyncio.sleep(SEND_DELAY)
#             _send_queue.task_done()
#
#
#
# # Безопасная отправка
# async def _safe_send(
#     bot: Bot,
#     telegram_id: int,
#     message: Message,
# ) -> None:
#     # копирование поста в бот (forward_message)
#     await bot.forward_message(
#         chat_id=telegram_id,
#         from_chat_id=message.chat.id,
#         message_id=message.message_id,
#     )
#
#
#
# # Добавление в очередь
# async def enqueue_send(telegram_id: int, message: Message) -> None:
#     await _send_queue.put((telegram_id, message))


