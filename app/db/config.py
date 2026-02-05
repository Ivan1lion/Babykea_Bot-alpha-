import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.models import Base



# Создаём движок и фабрику сессий
engine = create_async_engine(
    os.getenv("DB_URL"),
    echo=False,             # Отключаем логи в консоль
    pool_size=20,           # Увеличиваем пул
    max_overflow=10         # Доп. слоты при нагрузке
)
session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


