from sqlalchemy import select

from aiogram.types import Message
from app.posting.dto import PostingContext
from app.posting.queue import enqueue_send
from app.db.config import session_maker
from app.db.models import User



# Точка входа
async def dispatch_post(
    context: PostingContext,
    message: Message,
) -> None:
    async with session_maker() as session:
        users = await _get_target_users(session, context)

    for telegram_id in users:
        await enqueue_send(telegram_id, message)


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
