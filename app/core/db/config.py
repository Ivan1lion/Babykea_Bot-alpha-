import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.db.models import Base


# Создаём движок и фабрику сессий
engine = create_async_engine(
    os.getenv("DB_URL"),
    echo=False,             # Отключаем логи в консоль
    pool_size=20,           # Базовый пул соединений
    max_overflow=10,        # Доп. слоты при нагрузке (итого макс. 30 соединений)
    connect_args={
        "command_timeout": 30,  # Макс. время выполнения SQL-запроса (сек).
                                # 30 сек — запас для воркера ТО (UPDATE по всем юзерам).
                                # Простые SELECT/UPDATE по индексу выполняются за <100 мс.
        "timeout": 10           # Макс. время ожидания свободного слота в пуле (сек).
                                # При pool_size=20 + max_overflow=10 = 30 соединений.
                                # Если все 30 заняты >10 сек — бросаем ошибку, не висим вечно.
    }
)
session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
