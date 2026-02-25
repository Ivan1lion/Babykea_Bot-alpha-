from aiogram.types import Message
from sqlalchemy import select

from app.core.db.config import session_maker
from app.core.db.models import MagazineChannel, MyChannel, TechChannel
from app.platforms.telegram.posting.dto import PostingContext


async def resolve_channel_context(message: Message) -> PostingContext | None:
    """
    Определяет тип канала: Магазин, Авторский или Технический.
    """
    channel_id = message.chat.id

    async with session_maker() as session:
        # 1. Проверяем - это Технический канал? (Самый быстрый чек)
        tech = await session.execute(select(TechChannel).where(TechChannel.channel_id == channel_id))
        if tech.scalar_one_or_none():
            return PostingContext(source_type="tech", channel_id=channel_id)

        # 2. Проверяем - это канал Магазина?
        mag_stmt = select(MagazineChannel).where(MagazineChannel.channel_id == channel_id,
                                                 MagazineChannel.is_active == True)
        mag_channel = (await session.execute(mag_stmt)).scalar_one_or_none()

        if mag_channel:
            return PostingContext(
                source_type="magazine",
                channel_id=channel_id,
                magazine_id=mag_channel.magazine_id
            )

        # 3. Проверяем - это Твой Авторский канал?
        my_stmt = select(MyChannel).where(MyChannel.channel_id == channel_id, MyChannel.is_active == True)
        if (await session.execute(my_stmt)).scalar_one_or_none():
            return PostingContext(source_type="author", channel_id=channel_id)

    return None
