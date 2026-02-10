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
    if context.source_type == "tech":
        await cache_media_from_post(message)
        return

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

    # 1. Проверяем ХЭШТЕГ (в тексте или подписи)
    content_text = message.text or message.caption or ""
    has_hashtag = "#babykea" in content_text.lower()

    # 2. Проверяем ОПРОС (Poll)
    # У опросов нет caption, поэтому их нельзя пометить хэштегом
    is_poll = message.poll is not None

    # 3. Проверяем РЕПОСТ (Forward)
    # Если ты переслал пост к себе в канал, у него будет поле forward_date
    is_repost = message.forward_date is not None

    # ИТОГОВОЕ РЕШЕНИЕ:
    # Пересылаем (Forward), если выполняется ХОТЯ БЫ ОДНО условие
    should_forward = has_hashtag or is_poll or is_repost

    # Запускаем рассылку
    asyncio.create_task(
        start_broadcast(
            bot=bot,
            user_ids=list(user_ids),
            from_chat_id=context.channel_id,
            message_id=message.message_id,
            should_forward=should_forward  # 👈 Передаем наш умный флаг
        )
    )