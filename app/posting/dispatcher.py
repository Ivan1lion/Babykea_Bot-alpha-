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
    # СЦЕНАРИЙ 1: Технический канал -> Сохраняем в Redis и выходим (Рассылки НЕТ)
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

        # Если source_type == "author", то фильтров нет (идут все User.is_active)

        result = await session.execute(stmt)
        user_ids = result.scalars().all()

    if not user_ids:
        return

    # Запускаем в фоне безопасную рассылку
    asyncio.create_task(
        start_broadcast(
            bot=bot,
            user_ids=list(user_ids),  # Передаем готовый список
            from_chat_id=context.channel_id,
            message_id=message.message_id
        )
    )