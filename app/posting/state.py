from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.config import session_maker
from app.db.models import ChannelState, MyPost
from app.posting.dto import PostingContext




# Точка входа
async def is_new_post(
    context: PostingContext,
    message_id: int,
) -> bool:
    async with session_maker() as session:
        if context.source_type == "magazine":
            return await _check_magazine_channel_post(
                session=session,
                context=context,
                message_id=message_id,
            )

        if context.source_type == "my_channel":
            return await _check_my_channel_post(
                session=session,
                context=context,
                message_id=message_id,
            )

    return False



# Каналы магазинов (channel_states)
# Важно:
# одна строка = последний пост канала

async def _check_magazine_channel_post(
    session,
    context: PostingContext,
    message_id: int,
) -> bool:
    stmt = (
        select(ChannelState.post_id)
        .where(ChannelState.channel_id == context.channel_id)
        .limit(1)
    )

    result = await session.execute(stmt)
    last_post_id = result.scalar_one_or_none()

    # Пост старый или дубликат
    if last_post_id is not None and message_id <= last_post_id:
        return False

    # UPSERT: обновляем только если post_id больше
    upsert_stmt = (
        insert(ChannelState)
        .values(
            channel_id=context.channel_id,
            post_id=message_id,
            magazine_id=context.magazine_id,
        )
        .on_conflict_do_update(
            index_elements=[ChannelState.channel_id],
            set_={"post_id": message_id},
        )
    )

    await session.execute(upsert_stmt)
    await session.commit()

    return True




# Мои каналы (my_posts)
async def _check_my_channel_post(
    session,
    context: PostingContext,
    message_id: int,
) -> bool:
    stmt = (
        select(MyPost.post_id)
        .where(MyPost.channel_id == context.channel_id)
        .limit(1)
    )

    result = await session.execute(stmt)
    last_post_id = result.scalar_one_or_none()

    if last_post_id is not None and message_id <= last_post_id:
        return False

    upsert_stmt = (
        insert(MyPost)
        .values(
            channel_id=context.channel_id,
            post_id=message_id,
        )
        .on_conflict_do_update(
            index_elements=[MyPost.channel_id],
            set_={"post_id": message_id},
        )
    )

    await session.execute(upsert_stmt)
    await session.commit()

    return True


