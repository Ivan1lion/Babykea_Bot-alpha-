from sqlalchemy import update
from app.core.db.config import session_maker
from app.core.db.models import User


async def deactivate_user(telegram_id: int) -> None:
    async with session_maker() as session:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_active=False)
        )
        await session.execute(stmt)
        await session.commit()
