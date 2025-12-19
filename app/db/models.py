from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.sql import func
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey
from typing import Optional


# Кастомный Base-класс с таймстемпом
class Base(AsyncAttrs, DeclarativeBase):
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Таблица для магазина
class Magazine(Base):
    __tablename__ = "magazines"

    id: Mapped[int] = mapped_column(primary_key=True)

    promo_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )

    store_name: Mapped[str] = mapped_column(String(150), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    store_address: Mapped[str] = mapped_column(String(255), nullable=True)
    website: Mapped[str] = mapped_column(String(255), nullable=True)




# Таблица пользователя
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    promo_code: Mapped[str] = mapped_column(String(150), nullable=True)

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False
    )
    username: Mapped[str] = mapped_column(String(150), nullable=True)

    magazine_id: Mapped[int] = mapped_column(
        ForeignKey("magazines.id"),
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True)



    # id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # promo_code: Mapped[str] = mapped_column(String(150), nullable=True)
    # telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    # username: Mapped[str] = mapped_column(String(150), nullable=True)
    # thread_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=True)
    # requests_left: Mapped[int] = mapped_column(Integer, default=3)
    # request_status: Mapped[str] = mapped_column(String(20), default="idle")
    # email: Mapped[str] = mapped_column(String(128), default="idle")
    # auto_post: Mapped[str] = mapped_column(String(128), default="idle")
    # slot1: Mapped[str] = mapped_column(String(128), default="idle")
    # slot2: Mapped[int] = mapped_column(Integer, default=0)



# Таблица для постинга
class MagazineChannel(Base):
    __tablename__ = "magazine_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    magazine_id: Mapped[int] = mapped_column(ForeignKey("magazines.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)



# Таблица для постинга
class ChannelState(Base):
    __tablename__ = "channel_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    post_id: Mapped[int] = mapped_column(nullable=False)
    magazine_id: Mapped[int] = mapped_column(ForeignKey("magazines.id"), nullable=False)

    # last_post_id: Mapped[int] = mapped_column(Integer, default=0)
