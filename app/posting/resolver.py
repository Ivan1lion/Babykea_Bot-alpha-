from aiogram.types import Message
from sqlalchemy import select

from app.db.config import session_maker
from app.db.models import MagazineChannel, MyChannel
from app.posting.dto import PostingContext


async def resolve_channel_context(message: Message) -> PostingContext | None:
    """
    Определяет контекст постинга по Telegram channel_id
    """
    channel_id = message.chat.id

    async with session_maker() as session:
        # 1. Проверяем — канал магазина
        context = await _resolve_magazine_channel(session, channel_id)
        if context:
            return context

        # 2. Проверяем — мой личный канал
        context = await _resolve_my_channel(session, channel_id)
        if context:
            return context

    return None



# Каналы магазинов
async def _resolve_magazine_channel(
    session,
    channel_id: int,
) -> PostingContext | None:
    stmt = (
        select(MagazineChannel)
        .where(
            MagazineChannel.channel_id == channel_id,
            MagazineChannel.is_active.is_(True),
        )
        .limit(1)
    )

    result = await session.execute(stmt)
    channel = result.scalar_one_or_none()

    if not channel:
        return None

    return PostingContext(
        source_type="magazine",
        channel_id=channel.channel_id,
        magazine_id=channel.magazine_id,
        user_group=channel.channel_type,  # group_1 | group_2
        is_active=channel.is_active,
    )



# Mои личные каналы
async def _resolve_my_channel(
    session,
    channel_id: int,
) -> PostingContext | None:
    stmt = (
        select(MyChannel)
        .where(
            MyChannel.channel_id == channel_id,
            MyChannel.is_active.is_(True),
        )
        .limit(1)
    )

    result = await session.execute(stmt)
    channel = result.scalar_one_or_none()

    if not channel:
        return None

    return PostingContext(
        source_type="my_channel",
        channel_id=channel.channel_id,
        magazine_id=None,
        user_group="all",
        is_active=channel.is_active,
    )

