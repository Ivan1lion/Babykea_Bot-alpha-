import asyncio
import logging
from typing import List
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest
from app.posting.errors import deactivate_user

BATCH_SIZE = 25
RATE_LIMIT = 1.05

logger = logging.getLogger(__name__)


async def start_broadcast(bot: Bot, user_ids: List[int], from_chat_id: int, message_id: int):
    """Рассылает сообщение списку user_ids"""
    total = len(user_ids)
    sent = 0

    # Разбиваем на пачки
    for i in range(0, total, BATCH_SIZE):
        batch = user_ids[i: i + BATCH_SIZE]

        # Отправляем пачку
        success_count = await _send_batch(bot, batch, from_chat_id, message_id)
        sent += success_count

        # Пауза между пачками
        await asyncio.sleep(RATE_LIMIT)

    logger.info(f"📢 Рассылка завершена. Отправлено: {sent} из {total}")


async def _send_batch(bot: Bot, user_ids: List[int], from_chat_id: int, message_id: int) -> int:
    tasks = []
    for tg_id in user_ids:
        tasks.append(_safe_send(bot, tg_id, from_chat_id, message_id))

    results = await asyncio.gather(*tasks)
    return sum(results)


async def _safe_send(bot: Bot, user_id: int, from_chat_id: int, message_id: int) -> int:
    try:
        await bot.copy_message(chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id)
        return 1
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        return await _safe_send(bot, user_id, from_chat_id, message_id)
    except (TelegramForbiddenError, TelegramBadRequest):
        await deactivate_user(user_id)
        return 0
    except Exception as e:
        logger.error(f"Ошибка отправки {user_id}: {e}")
        return 0