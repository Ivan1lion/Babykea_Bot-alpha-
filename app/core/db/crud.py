import os
import asyncio
# from decimal import Decimal
# from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
# from openai import AsyncOpenAI

from app.db.models import User, Payment
from app.services.user_service import get_user_cached

# # Инициализируем OpenAI клиента один раз
# client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# # для постинга
# channel = int(os.getenv("CHANNEL_ID"))



# Не давать доступ к МЕНЮ если не введен промо-код
async def closed_menu(message: Message, session: AsyncSession, delete_delay: int = 1) -> bool:
    # 1. Достаем юзера из КЭША (Redis)
    # Если его там нет, функция сама сходит в БД и сохранит в кэш
    user = await get_user_cached(session, message.from_user.id)

    # 2. Проверяем флаг (берем из объекта кэша)
    # Если юзера нет или флаг False (меню открыто) -> пропускаем
    if not user or not user.closed_menu_flag:
        return False

        # 3. Если флаг True (меню закрыто) -> блокируем
    await message.delete()
    warn_message = await message.answer("Завершите действие⤴️")
    await asyncio.sleep(delete_delay)
    await warn_message.delete()
    return True



###  ###  ###  Для БД ###  ###  ###

# Получить пользователя или создать нового
async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_active = True
        user.username = username
        # Здесь коммит можно оставить, так как эта функция часто вызывается атомарно,
        # НО лучше тоже вынести. В данном случае для user оставляю как есть, если не вызывает ошибок,
        # но для чистоты лучше управлять снаружи.
        await session.commit()
        await session.refresh(user)
        return user

    new_user = User(
        telegram_id=telegram_id,
        username=username,
        requests_left=1,
        is_active=True,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user

###  ###  ###  Функции для платежей (БЕЗ COMMIT) ###  ###  ###

async def update_receipt_url(session: AsyncSession, payment_id: str, receipt_url: str):
    await session.execute(
        update(Payment)
        .where(Payment.payment_id == payment_id)
        .values(receipt_url=receipt_url)
    )
    # commit убран, делает вызывающий код

async def get_payment_by_payment_id(session: AsyncSession, payment_id: str) -> Payment | None:
    result = await session.execute(
        select(Payment).where(Payment.payment_id == payment_id)
    )
    return result.scalar_one_or_none()

async def create_pending_payment(session: AsyncSession, payment_id: str, telegram_id: int, amount):
    payment = Payment(
        payment_id=payment_id,
        telegram_id=telegram_id,
        amount=amount,
        status="pending",
    )
    session.add(payment)
    # commit убран

async def mark_payment_succeeded(session: AsyncSession, payment_id: str, receipt_url: str | None):
    await session.execute(
        update(Payment)
        .where(Payment.payment_id == payment_id)
        .values(
            status="succeeded",
            receipt_url=receipt_url,
        )
    )
    # commit убран

async def mark_payment_canceled(session: AsyncSession, payment_id: str):
    await session.execute(
        update(Payment)
        .where(Payment.payment_id == payment_id)
        .values(status="canceled")
    )
    # commit убран

async def mark_payment_failed(session: AsyncSession, payment_id: str):
    await session.execute(
        update(Payment)
        .where(Payment.payment_id == payment_id)
        .values(status="failed")
    )
    # commit убран

# Увеличить количество запросов к AI
async def increment_requests(session: AsyncSession, telegram_id: int, count: int):
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(requests_left=User.requests_left + count)
    )
    # commit убран


# === ФУНКЦИЯ ДЛЯ ПРЕМИУМ ДОСТУПА ===
async def activate_premium_subscription(session: AsyncSession, telegram_id: int, count: int):
    """
    Активирует полный доступ:
    1. Начисляет запросы
    2. Привязывает к техническому магазину (ID 1)
    3. Устанавливает промокод
    4. Открывает доступ к меню (снимает флаг)
    """
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(
            requests_left=User.requests_left + count,
            magazine_id=1,                 # Технический магазин
            promo_code='BABYKEA_PREMIUM',  # Спец код
            closed_menu_flag=False,        # 🔥 Снимаем флаг (даем доступ к меню)
            first_catalog_request=False    # 🔥 Снимаем флаг для первого ответа по поиску (что бы не было промо в ответе)
        )
    )