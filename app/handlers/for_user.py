import os
import asyncio
import random
import string
from uuid import uuid4
import aiohttp
import base64
import contextlib
import logging
import json


from aiogram import F, Router, types, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import Message, FSInputFile, CallbackQuery, InputMediaPhoto, PreCheckoutQuery, ContentType, SuccessfulPayment
from aiogram.enums import ParseMode
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal


import app.handlers.keyboards as kb
from app.handlers.keyboards import payment_button_keyboard
from app.db.crud import get_or_create_user, stop_if_no_promo, create_pending_payment
from app.db.models import User, MagazineChannel, ChannelState, Magazine, Payment, UserQuizProfile
from app.db.config import session_maker
from app.posting.resolver import resolve_channel_context
from app.posting.state import is_new_post
from app.posting.dispatcher import dispatch_post
from app.openai_assistant.responses_client import ask_responses_api
from app.payments.pay_config import PAYMENTS



for_user_router = Router()
logger = logging.getLogger(__name__)
# channel = int(os.getenv("CHANNEL_ID"))

class ActivationState(StatesGroup):
    waiting_for_promo_code = State()


# команд СТАРТ
@for_user_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, session: AsyncSession):
    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=-1003498991864, # ID группы
            message_id=4,  # ID сообщения из группы
            reply_markup=kb.quiz_start
        )
    except Exception as e:
        # Получаем абсолютный путь к медиа-файлу
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        GIF_PATH = os.path.join(BASE_DIR, "..", "mediafile_for_bot", "video.mp4")
        gif_file = FSInputFile(GIF_PATH)
        # Отправляем медиа
        wait_msg = await message.answer_video(video=gif_file, supports_streaming=True, reply_markup=kb.quiz_start)




# ОБРАБОТЧИКИ
@for_user_router.message(~(F.text))
async def filter(message: Message):
    await message.delete()
    await message.answer("Запросы AI консультанту только в формате текста")




@for_user_router.callback_query(F.data == "kb_activation")
async def activation(call: CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)

    await call.message.answer(
        "Вы можете оплатить доступ к боту или активировать его по промо-коду",
        reply_markup=kb.activation_kb,
    )
    await call.answer()






@for_user_router.callback_query(F.data == "enter_promo")
async def enter_promo(call: CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup(reply_markup=None)

    await state.set_state(ActivationState.waiting_for_promo_code)

    await call.message.answer("Введите код активации текстом:")
    await call.answer()




@for_user_router.message(StateFilter(ActivationState.waiting_for_promo_code), F.text)
async def process_promo_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
):
    promo_code = message.text.strip().upper()

    result = await session.execute(
        select(Magazine).where(Magazine.promo_code == promo_code)
    )
    magazine = result.scalar_one_or_none()

    if not magazine:
        await message.answer("Увы, данный код не действителен")
        return

    # обновляем пользователя
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one()

    user.promo_code = promo_code
    user.magazine_id = magazine.id

    await session.commit()

    await state.clear()

    await message.answer(f'✅ Проведена успешная активация по промокоду магазина детских колясок "{magazine.name}"\n\n'
                         f'Контакты продавца будут находиться в меню в разделе\n'
                         f'"📍 Магазин колясок"')
    await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=-1003498991864,  # ID группы
            message_id=4,  # ID сообщения из группы
            reply_markup=kb.instructions_for_bot
        )


######################### Обработка запросов пользователя к AI #########################


#Функция, чтобы крутился индикатор "печатает"
async def send_typing(bot, chat_id, stop_event):
    while not stop_event.is_set():
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(4.5)


@for_user_router.message(F.text)
async def handle_text(message: Message, session: AsyncSession, bot: Bot):
    # 1. Проверка промокода (твоя логика)
    if await stop_if_no_promo(message=message, session=session):
        return

    # 2. Получаем пользователя
    # Важно: нам нужно подгрузить связанные данные (магазин), если они не в одной таблице
    # Либо сделаем отдельными легкими запросами ниже.
    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = result.scalar_one_or_none()

    if not user:
        return  # Или ошибка "пользователь не найден"

    # 3. Проверка баланса
    if user.requests_left <= 0:
        await message.answer(
            f"🚫 У вас закончились запросы\n\n"
            f"Чтобы продолжить поиск, подбор и сравнение колясок - пополните запросы"
            f"\n\n<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
            "(Почему запросы платные?)</a>",
            reply_markup=kb.pay,
            disable_web_page_preview=True
        )
        return

    # --- СБОР ДАННЫХ ДЛЯ КОНТЕКСТА ---

    # А. Получаем URL магазина
    # Предполагаем, что у User есть поле magazine_id или promo_id, связывающее его с магазином
    shop_url = "https://market.yandex.ru"  # Дефолтный, если не найдем

    if user.magazine_id:  # Если связь через ID
        mag_result = await session.execute(select(Magazine.url_website).where(Magazine.id == user.magazine_id))
        shop_url = mag_result.scalar() or shop_url

    # Б. Получаем данные квиза (предпочтения пользователя)
    # JSONB обычно возвращается как dict в Python
    quiz_data_str = "Данные о предпочтениях отсутствуют."

    quiz_result = await session.execute(
        select(UserQuizProfile.data)  # Предполагаем поле 'data' с JSONB
        .where(UserQuizProfile.user_id == user.id)  # Или user.telegram_id, зависит от связи
        .order_by(UserQuizProfile.id.desc())  # Берем самый свежий квиз
        .limit(1)
    )
    quiz_data = quiz_result.scalar_one_or_none()

    if quiz_data:
        # Превращаем dict в красивую строку для промпта
        quiz_data_str = json.dumps(quiz_data, ensure_ascii=False, indent=2)

    # --- ФОРМИРОВАНИЕ СИСТЕМНОГО ПРОМПТА ---

    system_prompt = (
        "Ты профессиональный эксперт по подбору детских колясок. "
        "Твоя цель — помочь клиенту выбрать идеальную коляску, исходя из его потребностей.\n\n"

        f"📋 **ПРОФИЛЬ КЛИЕНТА (из анкеты):**\n{quiz_data_str}\n\n"

        f"🛒 **ИСТОЧНИК ТОВАРОВ:**\n"
        f"Ищи информацию и подбирай варианты ТОЛЬКО на сайте: {shop_url}\n"
        "Если пользователь спрашивает о конкретной модели, проверь её наличие и характеристики на этом сайте с помощью Google Search.\n\n"

        "**ИНСТРУКЦИИ:**\n"
        "1. Отвечай кратко, по делу, структурировано.\n"
        "2. Обязательно присылай ссылки на конкретные карточки товаров с указанного сайта.\n"
        "3. Используй форматирование Markdown (жирный шрифт, списки) для удобства чтения.\n"
        "4. Общайся вежливо и заботливо."
    )

    # --- ЗАПУСК ОБРАБОТКИ ---

    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(send_typing(bot, message.chat.id, stop_event))
    typing_msg = await message.answer("Ваш запрос обрабатывается и готовится ответ 💬")

    try:
        # 🔥 Вызов API с динамическим промптом
        answer = await ask_responses_api(
            user_message=message.text,
            system_instruction=system_prompt
        )

        # --- БЕЗОПАСНАЯ ОТПРАВКА СООБЩЕНИЯ (Anti-Crash) ---
        try:
            # Попытка 1: Отправляем красиво с Markdown
            await message.answer(answer, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        except TelegramBadRequest as e:
            # Если Telegram не смог переварить разметку Gemini
            logger.warning(f"Markdown parsing failed, sending plain text. Error: {e}")
            # Попытка 2: Отправляем чистым текстом (гарантированная доставка)
            await message.answer(answer, parse_mode=None, disable_web_page_preview=True)


        # ✅ Списание баланса (только при успехе)
        user.requests_left -= 1
        await session.commit()

    except Exception as e:
        logger.error(f"Ошибка в хэндлере: {e}", exc_info=True)
        await message.answer(
            '⚠️ Произошла ошибка при обработке запроса. '
            'Пожалуйста, повторите попытку позже.'
        )
    finally:
        # Убираем индикаторы
        stop_event.set()
        typing_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typing_task
        try:
            await typing_msg.delete()
        except:
            pass
# @for_user_router.message(F.text)
# async def handle_text(message: Message, session: AsyncSession, bot: Bot):
#     if await stop_if_no_promo(message=message, session=session):
#         return
#
#     result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
#     user = result.scalar_one_or_none()
#
#     if user.requests_left == 0:
#         await message.answer(f"🚫 У вас закончились запросы\n\n"
#                              f"Чтобы продолжить поиск, подбор и сравнение колясок - пополните запросы"
#                              f"\n\n<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
#                              "(Почему запросы платные?)</a>", reply_markup=kb.pay)
#         return
#
#     # Стартуем фоновый "набор текста"
#     stop_event = asyncio.Event()
#     typing_task = asyncio.create_task(send_typing(bot, message.chat.id, stop_event))
#
#     typing_msg = await message.answer("Ваш запрос обрабатывается и готовится ответ 💬")
#
#     try:
#         # 🔥 Вызов Responses API (запрос → ответ, без контекста)
#         answer = await ask_responses_api(message.text)
#         # Ответ пользователю от AI
#         await message.answer(answer, parse_mode=ParseMode.MARKDOWN)
#
#         # ✅ Запрос выполнен
#         user.requests_left -= 1
#         await session.commit()
#
#     except Exception as e:
#         await message.answer(f'⚠️ Ошибка при обработке запроса из-за проблем с интернет-соединением: {str(e)}\n\n'
#                              f'Повторите пожалуйста запрос позже')
#     finally:
#         # Убираем индикаторы
#         stop_event.set()
#         typing_task.cancel()
#         with contextlib.suppress(asyncio.CancelledError):
#             await typing_task
#         await typing_msg.delete()




######################### Приём платежа #########################
@for_user_router.callback_query(F.data.startswith("pay"))
async def process_payment(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
):
    telegram_id = callback.from_user.id
    cfg = PAYMENTS.get(callback.data)

    if not cfg:
        await callback.answer("Неизвестный тариф", show_alert=True)
        return

    amount = cfg["amount"]
    return_url = f"https://t.me/{(await bot.me()).username}"

    # ---------- проверяем пользователя ----------
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    # ---------- payload для YooKassa ----------
    payment_payload = {
        "amount": {
            "value": f"{amount:.2f}",
            "currency": "RUB",
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url,
        },
        "capture": True,
        "description": f"Оплата на сумму {amount} ₽",
        "metadata": {
            "telegram_id": str(telegram_id),
            "payment_type": callback.data,
        },
        "receipt": {
            "customer": {
                "email": "tobedrive@yandex.ru",
            },
            "tax_system_code": 2,
            "items": [
                {
                    "description": "Доступ к функционалу Telegram-бота",
                    "quantity": "1.00",
                    "measure": "service",
                    "amount": {
                        "value": f"{amount:.2f}",
                        "currency": "RUB",
                    },
                    "vat_code": 1,
                }
            ],
        },
    }

    # ---------- auth ----------
    def base64_auth():
        raw = f"{os.getenv('YOOKASSA_SHOP_ID')}:{os.getenv('YOOKASSA_SECRET_KEY')}"
        return base64.b64encode(raw.encode()).decode()

    headers = {
        "Authorization": f"Basic {base64_auth()}",
        "Content-Type": "application/json",
        "Idempotence-Key": str(uuid4()),
    }

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                "https://api.yookassa.ru/v3/payments",
                json=payment_payload,
                headers=headers,
            ) as resp:
                payment_response = await resp.json()

        print("📦 Ответ от ЮKassa:", payment_response)

        if "confirmation" not in payment_response:
            error_text = payment_response.get("description", "Нет confirmation")
            await callback.message.answer(f"❌ Ошибка ЮKassa: {error_text}")
            return

        payment_id = payment_response["id"]
        confirmation_url = payment_response["confirmation"]["confirmation_url"]

        # ===================== 🔴 ВАЖНО: ДОБАВЛЕНО =====================
        # сохраняем PENDING платёж в БД
        await create_pending_payment(
            session=session,
            payment_id=payment_id,
            telegram_id=telegram_id,
            amount=amount,
        )
        await session.commit()  # <--- ДОБАВЛЕН ЯВНЫЙ КОММИТ
        # ===============================================================

        await callback.message.answer(
            cfg["message"],
            reply_markup=payment_button_keyboard(confirmation_url),
        )
        await callback.answer()

    except Exception:
        logger.exception("Ошибка при создании платежа")
        await callback.message.answer(
            "❌ Ошибка при создании платежа. Попробуйте позже."
        )




# @for_user_router.callback_query(F.data.startswith("pay"))
# async def process_payment(
#     callback: CallbackQuery,
#     bot: Bot,
#     session: AsyncSession,
# ):
#     telegram_id = callback.from_user.id
#     cfg = PAYMENTS.get(callback.data)
#
#     if not cfg:
#         await callback.answer("Неизвестный тариф", show_alert=True)
#         return
#
#     amount = cfg["amount"]
#     return_url = f"https://t.me/{(await bot.me()).username}"
#
#     # ---------- проверяем пользователя ----------
#     result = await session.execute(
#         select(User).where(User.telegram_id == telegram_id)
#     )
#     user = result.scalar_one_or_none()
#     if not user:
#         return
#
#     # ---------- payload для YooKassa ----------
#     payment_payload = {
#         "amount": {
#             "value": f"{amount:.2f}",
#             "currency": "RUB",
#         },
#         "confirmation": {
#             "type": "redirect",
#             "return_url": return_url,
#         },
#         "capture": True,
#         "description": f"Оплата на сумму {amount} ₽",
#         "metadata": {
#             "telegram_id": str(telegram_id),
#             "payment_type": callback.data,
#         },
#         "receipt": {
#             "customer": {
#                 "email": "tobedrive@yandex.ru",
#             },
#             "tax_system_code": 2,
#             "items": [
#                 {
#                     "description": "Доступ к функционалу Telegram-бота",
#                     "quantity": "1.00",
#                     "measure": "service",
#                     "amount": {
#                         "value": f"{amount:.2f}",
#                         "currency": "RUB",
#                     },
#                     "vat_code": 1,
#                 }
#             ],
#         },
#     }
#
#     # ---------- auth ----------
#     def base64_auth():
#         raw = f"{os.getenv('YOOKASSA_SHOP_ID')}:{os.getenv('YOOKASSA_SECRET_KEY')}"
#         return base64.b64encode(raw.encode()).decode()
#
#     headers = {
#         "Authorization": f"Basic {base64_auth()}",
#         "Content-Type": "application/json",
#         "Idempotence-Key": str(uuid4()),
#     }
#
#     try:
#         async with aiohttp.ClientSession() as http:
#             async with http.post(
#                 "https://api.yookassa.ru/v3/payments",
#                 json=payment_payload,
#                 headers=headers,
#             ) as resp:
#                 payment_response = await resp.json()
#
#         print("📦 Ответ от ЮKassa:", payment_response)
#
#         if "confirmation" not in payment_response:
#             error_text = payment_response.get("description", "Нет confirmation")
#             await callback.message.answer(f"❌ Ошибка ЮKassa: {error_text}")
#             return
#
#         payment_id = payment_response["id"]
#         confirmation_url = payment_response["confirmation"]["confirmation_url"]
#
#         # ===================== 🔴 сохраняем PENDING платёж в БД =====================
#         await create_pending_payment(
#             session=session,
#             payment_id=payment_id,
#             telegram_id=telegram_id,
#             amount=amount,
#         )
#         # ===============================================================
#
#         await callback.message.answer(
#             cfg["message"],
#             reply_markup=payment_button_keyboard(confirmation_url),
#         )
#         await callback.answer()
#
#     except Exception:
#         logger.exception("Ошибка при создании платежа")
#         await callback.message.answer(
#             "❌ Ошибка при создании платежа. Попробуйте позже."
#         )





# @for_user_router.callback_query(F.data.startswith("pay"))
# async def process_payment(callback: CallbackQuery, bot: Bot, session: AsyncSession):
#     telegram_id = callback.from_user.id
#     amount_map = {
#         "pay29": 1,
#         "pay950": 950,
#         "pay190": 190
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
#         "description": f"Доступ к функционалу бота на сумму {amount} ₽",
#         "metadata": {
#             "telegram_id": str(telegram_id),
#             "payment_type": "bot_access",
#         },
#         "receipt": {
#             "customer": {
#                 "email": "tobedrive@yandex.ru"  # 🔴 ТВОЙ сервисный email
#             },
#             "tax_system_code": 2,  # 🔴 НПД (самозанятый)
#             "items": [
#                 {
#                     "description": "Доступ к функционалу Telegram-бота",
#                     "quantity": "1.00",
#                     "measure": "service",
#                     "amount": {
#                         "value": f"{amount:.2f}",
#                         "currency": "RUB"
#                     },
#                     "vat_code": 1,  # без НДС
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
#             f'\n\nПосле успешной оплаты, они отобразятся в разделе -> 🤖 AI-консультант'
#             f'\n\n<blockquote>Оплата производится через Yoomoney (Юkassa) - cервис безопасных платежей ПАО "Сбербанк"</blockquote>',
#             reply_markup=payment_button_keyboard(confirmation_url)
#         )
#         await callback.answer()
#
#     except Exception as e:
#         print("❌ Ошибка при создании платежа:", e)
#         await callback.message.answer("Ошибка при попытке создать платёж. Подробности в логах.")

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







# Отправка сообщений/постов из каналов

@for_user_router.channel_post()
async def channel_post_handler(message: Message) -> None:
    """
    Entry point для всех постов из каналов
    """

    # 1. Определяем: чей это канал и нужен ли он нам
    context = await resolve_channel_context(message)
    if context is None:
        return

    # 2. Проверяем — новый ли это пост
    if not await is_new_post(context, message.message_id):
        return

    # 3. Отправляем пост в очередь рассылки
    await dispatch_post(
        context=context,
        message=message,
    )





#Технический хендлер для определения id гифки
# @for_user_router.message()
# async def catch_animation(message: Message):
#     if message.animation:
#         await message.answer(
#             f"file_id:\n<code>{message.animation.file_id}</code>"
#         )
