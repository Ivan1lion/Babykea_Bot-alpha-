import asyncio
from aiogram import Bot
from aiogram.types import Message
from asyncio import Queue
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramRetryAfter,
)

from app.posting.errors import deactivate_user


SEND_RATE = 25
SEND_DELAY = 1 / SEND_RATE

_send_queue: Queue[tuple[int, Message]] = Queue()



# Основной sender
async def start_sender(bot: Bot) -> None:
    while True:
        telegram_id, message = await _send_queue.get()

        try:
            await _safe_send(bot, telegram_id, message)

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await _send_queue.put((telegram_id, message))

        except (TelegramForbiddenError, TelegramBadRequest):
            await deactivate_user(telegram_id)

        except Exception:
            # логирование добавишь позже
            pass

        finally:
            await asyncio.sleep(SEND_DELAY)
            _send_queue.task_done()



# Безопасная отправка
async def _safe_send(
    bot: Bot,
    telegram_id: int,
    message: Message,
) -> None:
    await bot.copy_message(
        chat_id=telegram_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )



# Добавление в очередь
async def enqueue_send(telegram_id: int, message: Message) -> None:
    await _send_queue.put((telegram_id, message))


