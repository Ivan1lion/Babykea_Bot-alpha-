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

    # --- 🚫 ФИЛЬТР: LIFESTYLE / NOBOT (ИГНОР) ---
    # 1. Сначала извлекаем текст
    content_text = message.text or message.caption or ""
    # 2. Переводим текст в нижний регистр один раз (для удобства)
    text_lower = content_text.lower()
    # 3. Проверяем: если есть "#lifestyle" ИЛИ "#nobot" — выходим
    if "#lifestyle" in text_lower or "#nobot" in text_lower:
        print(f"🙈 Пост {message.message_id} пропущен (фильтр)")
        return  # <--- Ключевой момент: Бот просто выходит из функции здесь

    # СЦЕНАРИЙ 2 и 3: Рассылка Юзерам
    async with session_maker() as session:
        # Базовое правило для ВСЕХ рассылок: бот должен быть НЕ заблокирован
        stmt = select(User.telegram_id).where(User.is_active == True)

        if context.source_type == "magazine":
            # Фильтр для магазина: шлем только подписчикам этого магазина
            stmt = stmt.where(User.magazine_id == context.magazine_id)

        elif context.source_type == "author":
            # Фильтр для автора: шлем только тем, кто не отписался от блога
            stmt = stmt.where(User.subscribed_to_author == True)

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

