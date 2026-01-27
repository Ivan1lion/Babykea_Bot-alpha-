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
from app.openai_assistant.prompts_config import get_system_prompt, get_marketing_footer
from app.payments.pay_config import PAYMENTS
from app.services.search_service import search_in_pinecone





logger = logging.getLogger(__name__)
for_user_router = Router()

# channel = int(os.getenv("CHANNEL_ID"))

class ActivationState(StatesGroup):
    waiting_for_promo_code = State()

class AIChat(StatesGroup):
    catalog_mode = State()  # Режим подбора (работает Pinecone / Feed)
    info_mode = State()     # Режим вопросов (работает Google Search / Общие знания)


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
    # await call.message.edit_reply_markup(reply_markup=None)
    await state.set_state(ActivationState.waiting_for_promo_code)
    await call.message.answer("Введите код активации текстом:")
    await call.answer()




@for_user_router.message(StateFilter(ActivationState.waiting_for_promo_code), F.text)
async def process_promo_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    delete_delay: int = 2
) -> bool:

    promo_code = message.text.strip().upper()

    result = await session.execute(
        select(Magazine).where(Magazine.promo_code == promo_code)
    )
    magazine = result.scalar_one_or_none()

    if not magazine:
        warn_promo = await message.answer("Увы, данный код не действителен или произошла ошибка соединения. Попробуйте ещё раз")
        await asyncio.sleep(delete_delay)
        await warn_promo.delete()
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
            # reply_markup=kb.
        )


######################### Обработка запросов пользователя к AI #########################


#Функция, чтобы крутился индикатор "печатает"
async def send_typing(bot, chat_id, stop_event):
    while not stop_event.is_set():
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(4.5)


# ==========================================
# 1. ОБРАБОТКА КНОПОК (ВЫБОР РЕЖИМА)
# ==========================================
@for_user_router.callback_query(F.data.in_({"mode_catalog", "mode_info"}))
async def process_mode_selection(callback: CallbackQuery, state: FSMContext):
    mode = callback.data

    if mode == "mode_catalog":
        await state.set_state(AIChat.catalog_mode)
        text = "👶 **Режим: Подбор коляски**\n\nОпишите, какую коляску вы ищете (например: *'Легкая для самолета'* или *'Вездеход для зимы'*)."
    else:
        await state.set_state(AIChat.info_mode)
        text = "❓ **Режим: Вопрос эксперту**\n\nЗадайте любой вопрос (например: *'Что лучше: Anex или Tutis?'* или *'Как смазать колеса?'*)."

    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


# ==========================================
# 2. ОБРАБОТКА ТЕКСТА (С УЧЕТОМ РЕЖИМА)
# ==========================================
@for_user_router.message(F.text, AIChat.catalog_mode)
@for_user_router.message(F.text, AIChat.info_mode)
async def handle_ai_message(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    # Проверки (промокод, баланс...)
    if await stop_if_no_promo(message=message, session=session): return

    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = result.scalar_one_or_none()
    if not user: return

    if user.requests_left <= 0:
        await message.answer(
            f"💡 Чтобы я мог выдать точный результат и завершить персональный анализ под ваши условия, выберите "
            f"пакет запросов ниже"
            f"\n\n<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
            "(Как это работает и что считается запросом?)</a>",
            reply_markup=kb.pay
        )
        return

    # Получаем текущий режим (state)
    current_state = await state.get_state()
    is_catalog_mode = (current_state == AIChat.catalog_mode.state)

    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(send_typing(bot, message.chat.id, stop_event))
    typing_msg = await message.answer("🤔 Думаю..." if not is_catalog_mode else "🔍 Ищу варианты...")

    try:
        # --- СБОР ДАННЫХ ---
        mag_result = await session.execute(select(Magazine).where(Magazine.id == user.magazine_id))
        current_magazine = mag_result.scalar_one_or_none()

        quiz_data_str = "Нет данных."
        quiz_json_obj = {}
        user_branch = "pregnant"  # Дефолт

        quiz_result = await session.execute(
            select(UserQuizProfile).where(UserQuizProfile.user_id == user.id).order_by(UserQuizProfile.id.desc()).limit(
                1)
        )
        quiz_profile = quiz_result.scalar_one_or_none()

        if quiz_profile:
            if quiz_profile.branch:
                user_branch = quiz_profile.branch
            try:
                if isinstance(quiz_profile.data, str):
                    quiz_json_obj = json.loads(quiz_profile.data)
                    quiz_data_str = quiz_profile.data
                else:
                    quiz_json_obj = quiz_profile.data
                    quiz_data_str = json.dumps(quiz_profile.data, ensure_ascii=False)
            except:
                pass

        # --- ЛОГИКА ПОИСКА (ТОЛЬКО ДЛЯ CATALOG MODE) ---
        products_context = ""
        final_shop_url = None

        if is_catalog_mode:
            # Тут работает Pinecone или Site Search
            if current_magazine:
                feed_url = current_magazine.feed_url

                if feed_url == "Google_Search":
                    final_shop_url = current_magazine.url_website
                elif feed_url:
                    # Поиск в базе по ID магазина
                    products_context = await search_in_pinecone(
                        user_query=message.text,
                        quiz_json=quiz_json_obj,
                        magazine_id=current_magazine.id,
                        top_k=10
                    )
                else:
                    # Поиск в базе везде (если нет фида у магазина, но режим подбора)
                    products_context = await search_in_pinecone(message.text, quiz_json_obj, None)
            else:
                products_context = await search_in_pinecone(message.text, quiz_json_obj, None)

        # Если режим INFO - мы просто пропускаем блок выше, products_context остается пустым,
        # и get_system_prompt выдаст шаблон эксперта.

        # --- ГЕНЕРАЦИЯ ---
        mode_key = "catalog_mode" if is_catalog_mode else "info_mode"

        system_prompt = get_system_prompt(
            mode=mode_key,
            quiz_data=quiz_data_str,
            shop_url=final_shop_url,
            products_context=products_context
        )

        answer = await ask_responses_api(
            user_message=message.text,
            system_instruction=system_prompt
        )

        # --- ФУТЕР (ТОЛЬКО ПЕРВЫЙ РАЗ) ---
        if user.is_first_request:
            marketing_footer = get_marketing_footer(user_branch)
            answer += marketing_footer
            user.is_first_request = False

        # --- ОТПРАВКА ---
        try:
            # 🔥 ВАЖНО: Используем HTML
            await message.answer(answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except TelegramBadRequest as e:
            # Если даже HTML сломался (очень редко), логируем и шлем текст
            logger.error(f"HTML Parse Error: {e}")
            await message.answer(answer, parse_mode=None, disable_web_page_preview=True)

        user.requests_left -= 1
        await session.commit()

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
    finally:
        stop_event.set()
        typing_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typing_task
        try:
            await typing_msg.delete()
        except:
            pass


# ==========================================
# 4. ЛОВУШКА ДЛЯ ТЕКСТА БЕЗ РЕЖИМА
# ==========================================
@for_user_router.message(F.text)
async def handle_no_state(message: Message, session: AsyncSession):
    """Если юзер пишет текст, но не выбрал кнопку -> показываем меню"""
    if await stop_if_no_promo(message=message, session=session):
        return

    await message.answer(
        "👋 Чтобы я мог помочь, выберите, пожалуйста, режим работы:",
        reply_markup=kb.get_ai_mode_kb()
    )



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
