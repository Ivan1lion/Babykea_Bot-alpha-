from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.models import User

async def update_user_email(session: AsyncSession, telegram_id: int, email: str):
    """Обновляет email пользователя."""
    stmt = (
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(email=email)
    )
    await session.execute(stmt)
    await session.commit()