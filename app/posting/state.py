import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
# from sqlalchemy.dialects.postgresql import insert

from app.db.config import session_maker
from app.db.models import MagazineChannel, MyChannel
from app.posting.dto import PostingContext

logger = logging.getLogger(__name__)


# Точка входа
async def is_new_post(
        context: PostingContext,
        message_id: int,
        message_date: datetime
) -> bool:
    """
    Проверяет, новый ли это пост.
    Если пост пришел, пока бот лежал (старый), он помечается как обработанный, но возвращает False (не слать).
    """

    # 1. Технический канал всегда обрабатываем (нам нужно обновить кэш, даже если бот лежал)
    if context.source_type == "tech":
        return True

    # 2. Проверка на "старость" (Recovery Mode)
    # Если посту больше 24 часа, мы считаем его устаревшим для рассылки
    # Но мы должны обновить базу, чтобы бот знал, что этот пост "видел"
    is_too_old = (datetime.now(timezone.utc) - message_date) > timedelta(hours=24)

    async with session_maker() as session:
        if context.source_type == "magazine":
            is_new = await _check_magazine_channel_post(session, context, message_id)
        elif context.source_type == "author":
            is_new = await _check_my_channel_post(session, context, message_id)
        else:
            return False

    if is_new and is_too_old:
        logger.warning(f"⚠️ Post {message_id} is too old (Date: {message_date}). Marking as read, skipping broadcast.")
        return False  # Не рассылаем

    return is_new


# --- Внутренние функции ---

async def _check_magazine_channel_post(session, context: PostingContext, message_id: int) -> bool:
    # 1. Получаем текущий last_post_id из таблицы канала магазина
    stmt = select(MagazineChannel.last_post_id).where(MagazineChannel.channel_id == context.channel_id)
    result = await session.execute(stmt)
    last_post_id = result.scalar_one_or_none()

    # Если канала нет в базе или пост старый — выходим
    if last_post_id is None:
        return False  # Странная ситуация, канал должен быть

    if message_id <= last_post_id:
        return False

    # 2. Обновляем ID (Простой UPDATE)
    update_stmt = (
        update(MagazineChannel)
        .where(MagazineChannel.channel_id == context.channel_id)
        .values(last_post_id=message_id)
    )
    await session.execute(update_stmt)
    await session.commit()
    return True


async def _check_my_channel_post(session, context: PostingContext, message_id: int) -> bool:
    # 1. Получаем текущий last_post_id из ТВОЕЙ таблицы
    stmt = select(MyChannel.last_post_id).where(MyChannel.channel_id == context.channel_id)
    result = await session.execute(stmt)
    last_post_id = result.scalar_one_or_none()

    if last_post_id is None:
        return False

    if message_id <= last_post_id:
        return False

    # 2. Обновляем ID
    update_stmt = (
        update(MyChannel)
        .where(MyChannel.channel_id == context.channel_id)
        .values(last_post_id=message_id)
    )
    await session.execute(update_stmt)
    await session.commit()
    return True