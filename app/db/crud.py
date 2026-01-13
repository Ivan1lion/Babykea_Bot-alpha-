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


                        ###  ###  ###  Не давать доступ к МЕНЮ если не введен промо-код ###  ###  ###


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

    warn_message = await message.answer("Закончите настройку⤴️")

    await asyncio.sleep(delete_delay)
    await warn_message.delete()

    return True


                                        ###  ###  ###  Для AI и БД ###  ###  ###

# Получить пользователя или создать нового + создание thread через OpenAI API
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
        # thread_id=thread.id, # 👈 это будет вида thread_abc123...
        is_active=True,  # обязательно активируем нового
    )

    # if user:
    #     # Создаём новый thread через OpenAI API
    #     thread = await client.beta.threads.create()
    #     if not thread or not thread.id:
    #         await message.answer("❌ Не удалось обновить сессию. Попробуйте позже.")
    #         raise RuntimeError("❌ Не удалось создать thread через OpenAI API")
    #
    #     # Обновляем thread_id у существующего пользователя
    #     user.thread_id = thread.id
    #     await session.commit()
    #     await session.refresh(user)
    #     return user
    #
    # # Новый пользователь → создать thread через OpenAI
    # thread = await client.beta.threads.create()
    # if not thread or not thread.id:
    #     await message.answer("❌ Не удалось обновить сессию. Попробуйте позже.")
    #     raise RuntimeError("❌ Не удалось создать thread через OpenAI API")

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user




# Уменьшить количество оставшихся запросов к AI
async def decrement_requests(session: AsyncSession, telegram_id: int) -> None:
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(requests_left=User.requests_left - 1)
    )
    await session.commit()

# Увеличить количество запросов к AI
async def increment_requests(session: AsyncSession, telegram_id: int, count: int):
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(requests_left=User.requests_left + count)
    )
    await session.commit()



# на случай перезагрузки/сбоя бота при отправки запроса к AI
async def notify_pending_users(bot: Bot, session_factory):
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.request_status == 'pending'))
        users = result.scalars().all()
        for user in users:
            try:
                await bot.send_message(user.telegram_id, f"⚠️ Извините, сбой на сервере"
                                                         f"\n\nПредыдущий запрос не был "
                                                         "обработан. Повторите его пожалуйста")
                user.status = 'error'
            except Exception as e:
                print(f"Ошибка при уведомлении пользователя {user.telegram_id}: {e}")
        await session.commit()





