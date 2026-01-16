import os
import asyncio

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI
from .models import User
from app.db.models import ChannelState, MagazineChannel, MyChannel, User



# Инициализируем OpenAI клиента один раз
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#для постинга
channel = int(os.getenv("CHANNEL_ID"))


# Не давать доступ к МЕНЮ если не введен промо-код
async def stop_if_no_promo(
    message: Message,
    session: AsyncSession,
    delete_delay: int = 1,
) -> bool:
    result = await session.execute(
        select(User.promo_code).where(
            User.telegram_id == message.from_user.id
        )
    )
    promo_code = result.scalar_one_or_none()

    if promo_code:
        return False  # НЕ останавливаем хэндлер

    # promo_code пустой → останавливаем
    await message.delete()

    warn_message = await message.answer("Завершите настройку⤴️")

    await asyncio.sleep(delete_delay)
    await warn_message.delete()

    return True


                                        ###  ###  ###  Для БД ###  ###  ###

# Получить пользователя или создать нового
async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None,) -> User:
    # Проверка: есть ли пользователь
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        # 2️⃣ Если есть, активируем и обновляем username
        user.is_active = True
        user.username = username
        await session.commit()
        await session.refresh(user)
        return user

        # 3️⃣ Если нет, создаём нового
    new_user = User(
        telegram_id=telegram_id,
        username=username,
        requests_left=1,
        is_active=True,  # обязательно активируем нового
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user




# Увеличить количество запросов к AI
async def increment_requests(session: AsyncSession, telegram_id: int, count: int):
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(requests_left=User.requests_left + count)
    )
    await session.commit()
