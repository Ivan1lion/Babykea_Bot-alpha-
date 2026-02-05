from sqlalchemy import select

from aiogram.types import Message
from app.posting.dto import PostingContext
from app.db.config import session_maker
from app.db.models import User
from app.posting.queue import start_broadcast
from app.db.config import session_maker



# Точка входа
async def dispatch_post(
    context: PostingContext,
    message: Message,
) -> None:
    async with session_maker() as session:
        users = await _get_target_users(session, context)

    asyncio.create_task(
        start_broadcast(
            bot=bot,
            session_maker=session_maker,
            from_chat_id=channel_id,
            message_id=message_id
        )
    )


# Получение целевых пользователей
async def _get_target_users(
    session,
    context: PostingContext,
) -> list[int]:
    stmt = select(User.telegram_id).where(User.is_active.is_(True))

    if context.source_type == "magazine":
        stmt = stmt.where(User.magazine_id == context.magazine_id)

    if context.user_group != "all":
        stmt = stmt.where(User.user_type == context.user_group)

    result = await session.execute(stmt)
    return result.scalars().all()
