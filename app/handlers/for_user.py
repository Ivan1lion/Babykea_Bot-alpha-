import os
import asyncio
import random
import string
from uuid import uuid4
import aiohttp
import base64

from aiogram import F, Router, types, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile, CallbackQuery, InputMediaPhoto, PreCheckoutQuery, ContentType, SuccessfulPayment
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


import app.handlers.keyboards as kb
from app.handlers.keyboards import payment_button_keyboard
from app.db.crud import get_or_create_user, get_last_post_id, set_last_post_id
from app.db.models import User
from app.db.config import session_maker
# from app.openai_assistant.client import ask_assistant
# from app.openai_assistant.queue import openai_queue


# channel = int(os.getenv("CHANNEL_ID"))

for_user_router = Router()




# команд СТАРТ
@for_user_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, session: AsyncSession):
    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    # # Проверяем auto_post
    # if user.auto_post == "idle":
    #     user.auto_post = "post_true"
    #     await session.commit()
    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=-1003498991864, # ID группы
            message_id=4,  # ID сообщения из группы
            reply_markup=kb.user_type
        )
    except Exception as e:
        # Получаем абсолютный путь к медиа-файлу
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        GIF_PATH = os.path.join(BASE_DIR, "..", "mediafile_for_bot", "video.mp4")
        gif_file = FSInputFile(GIF_PATH)
        # Отправляем медиа
        wait_msg = await message.answer_video(video=gif_file, supports_streaming=True, reply_markup=kb.user_type)



# ОБРАБОТЧИКИ


@for_user_router.callback_query(F.data == "user_type")
async def clear_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    # Получаем абсолютный путь к медиа-файлу
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    GIF_PATH = os.path.join(BASE_DIR, "..", "mediafile_for_bot", "My_photo.png")
    gif_file = FSInputFile(GIF_PATH)
    # Отправляем медиа
    await callback.message.answer_photo(photo=gif_file,caption=f'Выберете пожалуйста верное утверждение:'
                                                               f'\n\n1. Я в положении - ищу коляску для новорожденного'
                                                               f'\n\n2. Ищу прогулочную коляску для ребенка от 6 мес. и '
                                                               f'старше'
                                                               f'\n\n3. ')




@for_user_router.message(~(F.text))
async def filter(message: Message):
    await message.delete()
    await message.answer("Запросы AI консультанту только в формате текста")




######################### Обработка запросов пользователя к AI #########################


# Функция, чтобы крутился индикатор "печатает"
# async def send_typing(bot, chat_id, stop_event):
#     while not stop_event.is_set():
#         await bot.send_chat_action(chat_id=chat_id, action="typing")
#         await asyncio.sleep(4.5)
#
# @for_user_router.message(F.text)
# async def handle_text(message: Message, session: AsyncSession, bot: Bot):
#     result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
#     user = result.scalar_one_or_none()
#     if user.requests_left == 0:
#         await message.answer(f"🚫 У вас закончились запросы\n\nПожалуйста, пополните баланс"
#                              f"\n\n<a href='https://telegra.ph/pvapavp-07-04'>"
#                              "(Почему бот стал платным?)</a>", reply_markup=kb.pay)
#
#     if not openai_queue:
#         await message.answer("⚠️ Ассистент временно недоступен\n\nПовторите пожалуйста запрос позже")
#         return
#
#     try:
#         typing_msg = await message.answer("Ваш запрос обрабатывается и готовиться ответ 💬") # Отправляем текст
#
#         # 🟡 Обновляем статус запроса
#         user.request_status = "pending"
#         await session.commit()
#
#         # Стартуем фоновый "набор текста"
#         stop_event = asyncio.Event()
#         typing_task = asyncio.create_task(send_typing(bot, message.chat.id, stop_event))
#
#         answer = await ask_assistant(
#             queue=openai_queue,
#             user_id=user.telegram_id,
#             thread_id=user.thread_id,
#             message=message.text
#         )
#
#         # Убираем индикаторы
#         stop_event.set()
#         typing_task.cancel()
#         await typing_msg.delete()
#
#
#         await message.answer(answer, parse_mode=ParseMode.MARKDOWN)
#
#         # ✅ Запрос выполнен
#         user.requests_left -= 1
#         user.request_status = "complete"
#         await session.commit()
#     except Exception as e:
#         await message.answer(f'⚠️ Ошибка при обработке запроса: {str(e)}\n\nЕсли эта ошибка повторится сообщите '
#                              f'пожалуйста об этом администратору нашего сервиса '
#                              f'<a href="https://t.me/RomanMo_admin">@RomanMo_admin</a>')
#
#
#
#
# # Приём платежа
#
#
# def generate_random_email():   # Генерируем случайную строку длиной 10 символов
#     random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
#     return f"{random_str}@yandex.ru"
#
# @for_user_router.callback_query(F.data.startswith("pay"))
# async def process_payment(callback: CallbackQuery, bot: Bot, session: AsyncSession):
#     telegram_id = callback.from_user.id
#     amount_map = {
#         "pay30": 30,
#         "pay550": 550,
#         "pay2500": 2500
#     }
#
#     data_key = callback.data
#     amount = amount_map.get(data_key)
#     if not amount:
#         await callback.answer("Неизвестная сумма", show_alert=True)
#         return
#
#     return_url = f"https://t.me/{(await bot.me()).username}"
#
#
#     # Получаем пользователя
#     result = await session.execute(select(User).where(User.telegram_id == telegram_id))
#     user = result.scalar_one_or_none()
#     if not user:
#         return
#
#     # Генерируем email, если он ещё не задан
#     if not user.email or user.email == "idle":
#         user.email = generate_random_email()
#         await session.commit()
#
#     payment_payload = {
#         "amount": {
#             "value": f"{amount:.2f}",
#             "currency": "RUB"
#         },
#         "confirmation": {
#             "type": "redirect",
#             "return_url": return_url
#         },
#         "capture": True,
#         "description": f"Покупка на {amount}₽",
#         "metadata": {
#             "telegram_id": str(telegram_id)
#         },
#         "receipt": {
#             "customer": {
#                 "email": user.email
#             },
#             "items": [
#                 {
#                     "description": f"Покупка на {amount}₽",
#                     "quantity": "1.00",
#                     "amount": {
#                         "value": f"{amount:.2f}",
#                         "currency": "RUB"
#                     },
#                     "vat_code": 1
#                 }
#             ]
#         }
#     }
#     def base64_auth():
#         shop_id = os.getenv("YOOKASSA_SHOP_ID")
#         secret = os.getenv("YOOKASSA_SECRET_KEY")
#         raw = f"{shop_id}:{secret}".encode()
#         return base64.b64encode(raw).decode()
#
#     headers = {
#         "Authorization": f"Basic {base64_auth()}",
#         "Content-Type": "application/json",
#         "Idempotence-Key": str(uuid4())
#     }
#
#     try:
#         async with aiohttp.ClientSession() as session_http:
#             async with session_http.post(
#                 url="https://api.yookassa.ru/v3/payments",
#                 json=payment_payload,
#                 headers=headers
#             ) as resp:
#                 payment_response = await resp.json()
#
#         print("📦 Ответ от ЮKassa:", payment_response)
#
#         if "confirmation" not in payment_response:
#             error_text = payment_response.get("description", "Нет поля confirmation")
#             await callback.message.answer(f"❌ Ошибка ЮKassa: {error_text}")
#             return
#
#         confirmation_url = payment_response["confirmation"]["confirmation_url"]
#         await callback.message.answer(
#             f'Вы приобретаете дополнительные запросы'
#             f'\n\nПосле успешной оплаты, они отобразятся в разделе -> ⭐️ Баланс'
#             f'\n\n<blockquote>Оплата производится через Yoomoney (cервис электронных платежей ПАО "Сбербанк")</blockquote>',
#             reply_markup=payment_button_keyboard(confirmation_url)
#         )
#         await callback.answer()
#
#     except Exception as e:
#         print("❌ Ошибка при создании платежа:", e)
#         await callback.message.answer("Ошибка при попытке создать платёж. Подробности в логах.")
#
#
#
# # Отправка сообщений из канала Mari
#
# @for_user_router.channel_post()
# async def forward_post_to_users(message: Message, bot: Bot):
#     if message.chat.id != channel:
#         return
#
#     async with session_maker() as session:
#         last_id = await get_last_post_id(session)
#         if message.message_id <= last_id:
#             return  # уже отправляли пост
#
#         # Получаем всех пользователей
#         result = await session.execute(select(User.telegram_id))
#         users = result.scalars().all()
#
#         for user_id in users:
#             try:
#                 await bot.forward_message(
#                     chat_id=user_id,
#                     from_chat_id=channel,
#                     message_id=message.message_id,
#                 )
#             except Exception as e:
#                 print(f"❌ Ошибка отправки пользователю {user_id}: {e}")
#
#         # Обновляем last_post_id
#         await set_last_post_id(session, message.message_id)
#
#
#
#
#
