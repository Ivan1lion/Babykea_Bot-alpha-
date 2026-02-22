from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.sql import func
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Boolean, Numeric, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from typing import Optional
from decimal import Decimal


# Кастомный Base-класс с таймстемпом
class Base(AsyncAttrs, DeclarativeBase):
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


#1 Таблица для магазина
class Magazine(Base):
    __tablename__ = "magazines"

    id: Mapped[int] = mapped_column(primary_key=True)
    promo_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )
    is_promo_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    feed_url = Column(String, nullable=True)  # Ссылка на YML файл (может быть пустой - тогда ответы только из поиска)/ Если поставить "PREMIUM_AGGREGATOR", то идет поиск по всем фидам из векторной БД
    name: Mapped[str] = mapped_column(String(150), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(String(255), nullable=True)
    name_website: Mapped[str] = mapped_column(String(255), nullable=True)
    url_website: Mapped[str] = mapped_column(String(255), nullable=True)
    photo: Mapped[str] = mapped_column(String(500), nullable=True)
    map_url: Mapped[str] = mapped_column(String(500), nullable=True)
    username_magazine: Mapped[str] = mapped_column(String(150), nullable=True)




#2 Таблица пользователя
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
        nullable=True
    )
    email: Mapped[str] = mapped_column(String(150), nullable=True)
    stroller_model: Mapped[str] = mapped_column(String(50), nullable=True)
    requests_left: Mapped[int] = mapped_column(Integer, default=1)
    closed_menu_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    first_catalog_request: Mapped[bool] = mapped_column(Boolean, default=True)
    first_info_request: Mapped[bool] = mapped_column(Boolean, default=True)
    show_intro_message: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    subscribed_to_author: Mapped[bool] = mapped_column(default=True, server_default="true")
    wb_clicked_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)




#3 Профиль прохождения квиза пользователя
class UserQuizProfile(Base):
    __tablename__ = "user_quiz_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    branch: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    current_level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    data = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    completed_once: Mapped[bool] = mapped_column(default=False)





#4 Таблица для постинга. Каналы магазинов
class MagazineChannel(Base):
    __tablename__ = "magazine_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    magazine_id: Mapped[int] = mapped_column(ForeignKey("magazines.id", ondelete="CASCADE"), nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    last_post_id: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)







#5 Таблица для постинга из МОЕГО ЛИЧНОГО канала. Сдесь будет id моего канала
class MyChannel(Base):
    __tablename__ = "my_channels"

    id: Mapped[int] = mapped_column(primary_key=True)

    channel_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False
    )
    last_post_id: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)







#6 🔥 Технический канал (для загрузки файлов в Redis)
class TechChannel(Base):
    __tablename__ = "tech_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)  # Пометка чей это канал




#7 Таблица оплаты для решения дублей webhook
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    payment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    status: Mapped[str] = mapped_column(String(20))  # pending | succeeded | canceled | failed
    # failed → оплата не прошла
    # pending → создаётся при создании платежа
    # succeeded → успешная оплата
    # canceled → отменённая

    receipt_url: Mapped[str | None] = mapped_column(String, nullable=True)

