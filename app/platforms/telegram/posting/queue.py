import asyncio
import logging
from typing import List
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest
from app.platforms.telegram.posting.errors import deactivate_user

BATCH_SIZE = 20
RATE_LIMIT = 1.5

logger = logging.getLogger(__name__)


# 1. Добавляем аргумент should_forward
async def start_broadcast(
        bot: Bot,
        user_ids: List[int],
        from_chat_id: int,
        message_id: int,
        should_forward: bool = False
):
    """Рассылает сообщение списку user_ids"""
    total = len(user_ids)
    sent = 0

    for i in range(0, total, BATCH_SIZE):
        batch = user_ids[i: i + BATCH_SIZE]

        # Передаем флаг дальше
        success_count = await _send_batch(bot, batch, from_chat_id, message_id, should_forward)
        sent += success_count
        await asyncio.sleep(RATE_LIMIT)

    logger.info(f"📢 Рассылка завершена. Отправлено: {sent} из {total}")


# 2. И здесь добавляем аргумент
async def _send_batch(
        bot: Bot,
        user_ids: List[int],
        from_chat_id: int,
        message_id: int,
        should_forward: bool
) -> int:
    tasks = []
    for tg_id in user_ids:
        # Передаем флаг в финальную функцию
        tasks.append(_safe_send(bot, tg_id, from_chat_id, message_id, should_forward))

    results = await asyncio.gather(*tasks)
    return sum(results)


# 3. Реализуем логику выбора (Copy или Forward)
async def _safe_send(
        bot: Bot,
        user_id: int,
        from_chat_id: int,
        message_id: int,
        should_forward: bool
) -> int:
    try:
        if should_forward:
            # ПЕРЕСЫЛКА (видно "Forwarded from...")
            await bot.forward_message(chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id)
        else:
            # КОПИРОВАНИЕ (от имени бота)
            await bot.copy_message(chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id)

        return 1

    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        # Не забываем передать флаг при повторе
        return await _safe_send(bot, user_id, from_chat_id, message_id, should_forward)

    except (TelegramForbiddenError, TelegramBadRequest):
        await deactivate_user(user_id)
        return 0
    except Exception as e:
        logger.error(f"Ошибка отправки {user_id}: {e}")
        return 0