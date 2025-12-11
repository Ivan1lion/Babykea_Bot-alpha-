import os
from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI
from .models import User
from app.db.models import ChannelState


# Инициализируем OpenAI клиента один раз
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#для постинга
channel = int(os.getenv("CHANNEL_ID"))


# Получить пользователя или создать нового
async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str,) -> User:
    # Проверка: есть ли пользователь
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user:
        # Создаём новый thread через OpenAI API
        thread = await client.beta.threads.create()
        if not thread or not thread.id:
            await message.answer("❌ Не удалось обновить сессию. Попробуйте позже.")
            raise RuntimeError("❌ Не удалось создать thread через OpenAI API")

        # Обновляем thread_id у существующего пользователя
        user.thread_id = thread.id
        await session.commit()
        await session.refresh(user)
        return user



    # Новый пользователь → создать thread через OpenAI
    thread = await client.beta.threads.create()
    if not thread or not thread.id:
        await message.answer("❌ Не удалось обновить сессию. Попробуйте позже.")
        raise RuntimeError("❌ Не удалось создать thread через OpenAI API")

    new_user = User(
        telegram_id=telegram_id,
        username=username,
        thread_id=thread.id,  # 👈 это будет вида thread_abc123...
        requests_left=3,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


# Уменьшить количество оставшихся запросов
async def decrement_requests(session: AsyncSession, telegram_id: int) -> None:
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(requests_left=User.requests_left - 1)
    )
    await session.commit()

# Увеличить количество запросов
async def increment_requests(session: AsyncSession, telegram_id: int, count: int):
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(requests_left=User.requests_left + count)
    )
    await session.commit()





# на случай перезагрузки/сбоя бота
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





# добавление в базу номера последнего поста в канале
async def get_last_post_id(session):
    state = await session.get(ChannelState, 1)
    return state.last_post_id if state else 0

async def set_last_post_id(session, post_id: int):
    state = await session.get(ChannelState, 1)
    if state:
        state.last_post_id = post_id
    else:
        state = ChannelState(id=1, last_post_id=post_id)
        session.add(state)
    await session.commit()



# на случай перезагрузки/сбоя бота
async def fetch_and_send_unsent_post(bot: Bot, session: AsyncSession):
    try:
        last_sent_id = await get_last_post_id(session)
        candidate_id = last_sent_id + 1

        # Пробуем переслать сообщение самому себе — проверка, существует ли оно
        try:
            test_message = await bot.forward_message(
                chat_id=int(os.getenv("ADMIN_ID")),  # временно, для отладки
                from_chat_id=channel,
                message_id=candidate_id
            )
        except Exception:
            print("📭 Нет новых сообщений в канале")
            return

        # Получаем всех пользователей
        result = await session.execute(select(User.telegram_id))
        users = result.scalars().all()

        # Пересылаем каждому
        for user_id in users:
            try:
                await bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=channel,
                    message_id=candidate_id
                )
            except Exception as e:
                print(f"❌ Не удалось переслать {user_id}: {e}")

        await set_last_post_id(session, candidate_id)

    except Exception as e:
        print(f"❗ Ошибка при проверке последнего поста: {e}")