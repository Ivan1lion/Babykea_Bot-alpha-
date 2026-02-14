import asyncio
from sqlalchemy import select
from aiogram.types import Message
from aiogram import Bot

from app.db.config import session_maker
from app.db.models import User
from app.posting.dto import PostingContext
from app.posting.queue import start_broadcast
from app.posting.media_cache import cache_media_from_post


async def dispatch_post(context: PostingContext, message: Message, bot: Bot) -> None:
    # СЦЕНАРИЙ 1: Технический канал -> Сохраняем в Redis и выходим
    # (Технический канал обрабатываем первым, ему теги не важны)
    if context.source_type == "tech":
        await cache_media_from_post(message)
        return

    # --- 🚫 ФИЛЬТР: LIFESTYLE (ИГНОР) ---
    # 1. Сначала извлекаем текст (он нам пригодится и для проверки, и позже)
    content_text = message.text or message.caption or ""

    # 2. Если находим стоп-слово — полностью останавливаем работу функции
    if "#lifestyle" in content_text.lower():
        print(f"🙈 Пост {message.message_id} пропущен (lifestyle)")
        return  # <--- Ключевой момент: Бот просто выходит из функции здесь

    # СЦЕНАРИЙ 2 и 3: Рассылка Юзерам
    async with session_maker() as session:
        # Строим запрос пользователей
        stmt = select(User.telegram_id).where(User.is_active == True)

        if context.source_type == "magazine":
            # Фильтр: Только подписчики этого магазина
            stmt = stmt.where(User.magazine_id == context.magazine_id)

        result = await session.execute(stmt)
        user_ids = result.scalars().all()

    if not user_ids:
        return

    # --- 🔥 ЛОГИКА: КОГДА ДЕЛАТЬ FORWARD (ПЕРЕСЫЛКУ) ---

    # 1. Проверяем ХЭШТЕГ (для принудительного репоста)
    # (content_text мы уже получили выше, используем его)
    has_hashtag = "#babykea" in content_text.lower()

    # 2. Проверяем ОПРОС (Poll)
    is_poll = message.poll is not None

    # 3. Проверяем РЕПОСТ (Forward)
    is_repost = message.forward_date is not None

    # ИТОГОВОЕ РЕШЕНИЕ:
    should_forward = has_hashtag or is_poll or is_repost

    # Запускаем рассылку
    asyncio.create_task(
        start_broadcast(
            bot=bot,
            user_ids=list(user_ids),
            from_chat_id=context.channel_id,
            message_id=message.message_id,
            should_forward=should_forward
        )
    )