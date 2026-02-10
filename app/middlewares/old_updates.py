from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta, timezone
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update


class DropOldUpdatesMiddleware(BaseMiddleware):
    def __init__(self, limit_seconds: int = 60):
        """
        limit_seconds: Время в секундах. Если апдейт старее этого времени, он игнорируется.
        Для постов каналов это правило НЕ работает (пропускаем всегда).
        """
        self.limit = limit_seconds

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:

        # 1. Если это ПОСТ КАНАЛА — пропускаем всегда!
        # (У тебя там своя логика is_new_post на 24 час)
        if hasattr(event, "chat") and event.chat.type == "channel":
            return await handler(event, data)

        # 2. Определяем дату события
        event_date = None

        if isinstance(event, Message):
            event_date = event.date
        elif isinstance(event, CallbackQuery) and event.message:
            # Для колбэков берем дату сообщения, на котором нажали,
            # или текущую (если сообщение слишком старое, телеграм может не прислать дату)
            event_date = event.message.date

        # 3. Если дату нашли — проверяем "свежесть"
        if event_date:
            # Приводим к UTC (так как event.date обычно в UTC)
            now = datetime.now(timezone.utc)

            # Если событие старше лимита (например, 60 секунд)
            if (now - event_date) > timedelta(seconds=self.limit):
                print(f"🗑 Игнорирую старое обновление: {type(event).__name__} от {event_date}")
                return  # ⛔️ Просто выходим, не передавая управление хендлеру

        # Если всё ок — передаем дальше
        return await handler(event, data)