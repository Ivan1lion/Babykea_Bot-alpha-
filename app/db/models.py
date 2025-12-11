from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.sql import func
from sqlalchemy import BigInteger, Integer, String, DateTime
from typing import Optional


# Кастомный Base-класс с таймстемпом
class Base(AsyncAttrs, DeclarativeBase):
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Модель пользователя
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(150), nullable=True)
    thread_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=True)
    requests_left: Mapped[int] = mapped_column(Integer, default=3)
    request_status: Mapped[str] = mapped_column(String(20), default="idle")
    email: Mapped[str] = mapped_column(String(128), default="idle")
    auto_post: Mapped[str] = mapped_column(String(128), default="idle")
    slot1: Mapped[str] = mapped_column(String(128), default="idle")
    slot2: Mapped[int] = mapped_column(Integer, default=0)


# Модель для постинга
class ChannelState(Base):
    __tablename__ = "channel_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    last_post_id: Mapped[int] = mapped_column(Integer, default=0)
