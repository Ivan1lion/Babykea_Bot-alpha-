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
from app.db.crud import get_or_create_user, closed_menu, create_pending_payment
from app.db.models import User, Magazine, Payment, UserQuizProfile
from app.db.config import session_maker
from app.posting.resolver import resolve_channel_context
from app.posting.state import is_new_post
from app.posting.dispatcher import dispatch_post
from app.openai_assistant.responses_client import ask_responses_api
from app.openai_assistant.prompts_config import get_system_prompt, get_marketing_footer
from app.payments.pay_config import PAYMENTS
from app.services.search_service import search_products
from app.services.user_service import get_user_cached, update_user_requests, update_user_flags, try_reserve_request, refund_request
from app.redis_client import redis_client





logger = logging.getLogger(__name__)
for_user_router = Router()

tech_channel_id = int(os.getenv("TECH_CHANNEL_ID"))
start_post = int(os.getenv("START_POST"))
ai_post = int(os.getenv("AI_POST"))


class ActivationState(StatesGroup):
    waiting_for_promo_code = State()

class AIChat(StatesGroup):
    catalog_mode = State()  # Режим подбора (работает векторная БД)
    info_mode = State()     # Режим вопросов (работает Google Search / Общие знания)


# ID магазинов, по которым ищем для ПЛАТНЫХ пользователей
# 🔥🔥🔥🔥🔥🔥🔥🔥(Замени цифры на реальные ID твоих 5 крупных магазинов в БД)🔥🔥🔥🔥🔥🔥🔥🔥
TOP_SHOPS_IDS = [2]


# команд СТАРТ
@for_user_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, session: AsyncSession):
    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    # 1. Пытаемся отправить мгновенно через Redis (PRO способ)
    # Мы ищем file_id, который сохранили под именем "start_video"
    # === ПОПЫТКА 1: REDIS (безопасная) ===
    video_note_id = await redis_client.get("media:start_video")

    if video_note_id:
        try:
            await message.answer_video_note(
                video_note=video_note_id,
                reply_markup=kb.quiz_start
            )
            print(f"🔔 ПОПЫТКА 1: Redis)")
            return  # Успех, выходим
        except Exception as e:
            logger.error(f"Ошибка отправки video_note из Redis: {e}")

    # 2. FALLBACK 1: Если в Redis пусто, пробуем copy_message (Старый способ)
    # Это страховка на случай, если ты забыл загрузить видео в тех.канал
    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=tech_channel_id, # ID тех канала
            message_id=start_post,  # ID сообщения из группы
            reply_markup=kb.quiz_start
        )
        print(f"🔔 ПОПЫТКА 2: Пересылка из канала")
        return
    except Exception:
        pass  # Идем к самому надежному варианту

    # 3. FALLBACK 2: Если всё сломалось — файл с диска (Железобетонный вариант)
    # ВАЖНО: answer_video отправляет ПРЯМОУГОЛЬНИК.
    # Если нужен КРУЖОК с диска, используй answer_video_note (но файл должен быть квадратным 1:1)
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        # Убедись, что путь правильный
        VIDEO_PATH = os.path.join(BASE_DIR, "..", "mediafile_for_bot", "video.mp4")
        video_file = FSInputFile(VIDEO_PATH)

        # Если файл на диске - это обычное видео, используй answer_video
        await message.answer_video(
            video=video_file,
            supports_streaming=True,
            reply_markup=kb.quiz_start
        )
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Не удалось отправить приветствие: {e}")
        # Хотя бы текст отправим, чтобы бот не молчал
        await message.answer("Добро пожаловать!", reply_markup=kb.quiz_start)





# ОБРАБОТЧИКИ
@for_user_router.message(~(F.text))
async def filter(message: Message):
    await message.delete()
    await message.answer("Запросы AI консультанту только в формате текста")




@for_user_router.callback_query(F.data == "kb_activation")
async def activation(call: CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)

    await call.message.answer_photo(
        photo="AgACAgIAAyEGAATQjmD4AANnaY3ziPd3A8eUTwbZqo6-aqCuxmYAAmQaaxs1a3FI56_9NYQIxA0BAAMCAAN5AAM6BA",
        caption="<b>Оплатите полный доступ ко всем разделам за 1900₽</b> "
        "\n<i>(В пакет также включены 50 бесплатных запросов к AI-консультанту)</i>"
        "\n\n<blockquote>🎫 <b>Есть флаер от магазина-партнера?</b>  — нажмите «Ввести код активации» для свободного "
        "доступа к моим личным видеорекомендациям и реальным советам: как выбрать и не сломать коляску</blockquote>",
        reply_markup=kb.activation_kb,
    )
    await call.answer()






@for_user_router.callback_query(F.data == "enter_promo")
async def enter_promo(call: CallbackQuery, state: FSMContext):
    await state.set_state(ActivationState.waiting_for_promo_code)
    await call.message.answer("Введите код активации текстом:")
    await call.answer()




@for_user_router.message(StateFilter(ActivationState.waiting_for_promo_code), F.text)
async def process_promo_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot
):

    promo_code = message.text.strip().upper()

    result = await session.execute(
        select(Magazine).where(Magazine.promo_code == promo_code)
    )
    magazine = result.scalar_one_or_none()

    # 1. ПРОВЕРКА 1: Код вообще не найден (опечатка)
    if not magazine:
        await message.answer("⚠️ <b>Код не сработал</b>"
                             "\n\nЭто не вина магазина — Вам выдали действующий код, просто система иногда "
                             "может капризничать. Попробуйте ещё раз"
                             "\n\n<blockquote>Если опять не получится напишите мне @Master_PROkolyaski. Я лично проверю "
                             "ваш промокод и открою доступ к видео и советам вручную, чтобы вы могли "
                             "продолжить без лишних нервов</blockquote>"
                             )
        return

    # 2. ПРОВЕРКА 2: Код найден, но отключен (акция завершена is_promo_active = False)
    if not magazine.is_promo_active:
        await message.answer("У данного промокода истек срок активации.")
        return

    # 1. Обновляем пользователя (привязываем магазин)
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one()

    user.promo_code = promo_code
    user.magazine_id = magazine.id

    # 2. Узнаем branch пользователя (чтобы понять, какую кнопку дать)
    # Берем последний заполненный квиз
    quiz_result = await session.execute(
        select(UserQuizProfile.branch)
        .where(UserQuizProfile.user_id == user.id)
        .order_by(UserQuizProfile.id.desc())
        .limit(1)
    )
    branch = quiz_result.scalar_one_or_none()

    if branch == 'service_only':
        user.closed_menu_flag = False

    # 1. СОХРАНЯЕМ ДАННЫЕ В ПЕРЕМЕННЫЕ (До коммита!)
    mag_name = magazine.name
    raw_url = magazine.name_website

    # 2. КОММИТИМ
    await session.commit()
    # ==========================================================
    # 🔥 ЛЕКАРСТВО ОТ БАГА: СБРОС КЭША REDIS 🔥
    # Мы удаляем старую запись, где magazine_id был пустым.
    # Следующий запрос (get_user_cached) вынужден будет пойти в БД
    # и достать юзера уже с НОВЫМ ID магазина.
    # ==========================================================
    await redis_client.delete(f"user:{message.from_user.id}")
    logger.info(f"♻️ Кэш для юзера {message.from_user.id} успешно сброшен после активации промокода.")
    # ==========================================================
    await state.clear()

    # 3. УМНОЕ ФОРМИРОВАНИЕ ССЫЛКИ И ТЕКСТА
    # Проверяем: имя существует И оно НЕ равно "[Babykea]"
    if mag_name and mag_name != "[Babykea]":
        if raw_url:
            # Убираем пробелы (на всякий случай)
            clean_url = raw_url.strip()

            # Если ссылка НЕ начинается с http — приклеиваем https://
            if not clean_url.startswith("http"):
                final_url = f"https://{clean_url}"
            else:
                final_url = clean_url

            magazine_display = f'<a href="{final_url}">{mag_name}</a>'
        else:
            # Если ссылка пустая, но имя есть
            magazine_display = f'<b>{mag_name}</b>'

        # 4. ФИНАЛЬНЫЙ ТЕКСТ (Если магазин это партнера)
        success_text = (
            f'✅ Проведена успешная активация по промокоду магазина детских колясок {magazine_display}\n\n'
            f'Контакты продавца будут находиться в меню в разделе\n'
            f'[📍 Магазин колясок]'
            f'\n\nТеперь проверим бота в деле 👇'
        )
    else:
        # 4. ФИНАЛЬНЫЙ ТЕКСТ (Если имя магазина пустое / None или = "[Babykea]")
        success_text = ('✅ <b>Код принят! Добро пожаловать</b>'
                        '\n\nВы сделали верный шаг, чтобы сэкономить нервы при выборе коляски и уберечь свою '
                        'от дорогого ремонта в будущем'
                        '\n\nДавайте проверим бота в деле 👇')

    # 5. Отправка сообщения с нужной клавиатурой в зависимости от branch
    if branch == 'service_only':
        await message.answer(text=success_text, reply_markup=kb.rules_mode)
    else:
        # Стандартный вариант (кнопка "Подобрать коляску")
        await message.answer(text=success_text, reply_markup=kb.first_request)




######################### Обработка запросов пользователя к AI #########################


#Функция, чтобы крутился индикатор "печатает"
async def send_typing(bot, chat_id, stop_event):
    while not stop_event.is_set():
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(4.5)


# ==========================================
# 0. ОБРАБОТКА КНОПКИ "ПОДОБРАТЬ КОЛЯСКУ" (АВТО-ЗАПРОС)
# ==========================================

async def _run_auto_request_task(
    bot: Bot,
    chat_id: int,
    telegram_id: int,
    typing_msg_id: int,
    user_id: int,
    magazine_id,
    first_catalog_request: bool,
):
    """
    Фоновая задача для обработки авто-запроса "Подобрать коляску".
    Запускается через asyncio.create_task — хэндлер не ждёт её завершения,
    Telegram сразу получает 200 OK.
    Использует собственную сессию БД, т.к. сессия хэндлера закрывается раньше.
    """
    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(send_typing(bot, chat_id, stop_event))

    try:
        async with session_maker() as session:
            # --- СБОР ДАННЫХ О МАГАЗИНЕ ---
            mag_result = await session.execute(select(Magazine).where(Magazine.id == magazine_id))
            current_magazine = mag_result.scalar_one_or_none()

            # --- СБОР ДАННЫХ КВИЗА ---
            quiz_data_str = "Нет данных."
            quiz_json_obj = {}

            quiz_result = await session.execute(
                select(UserQuizProfile)
                .where(UserQuizProfile.user_id == user_id)
                .order_by(UserQuizProfile.id.desc())
                .limit(1)
            )
            quiz_profile = quiz_result.scalar_one_or_none()

            if quiz_profile:
                try:
                    if isinstance(quiz_profile.data, str):
                        quiz_json_obj = json.loads(quiz_profile.data)
                        quiz_data_str = quiz_profile.data
                    else:
                        quiz_json_obj = quiz_profile.data
                        quiz_data_str = json.dumps(quiz_profile.data, ensure_ascii=False)
                except Exception:
                    pass

            # --- ПОИСК В БАЗЕ ---
            products_context = ""
            final_shop_url = None

            if current_magazine:
                feed_url = current_magazine.feed_url

                if feed_url and "http" in feed_url:
                    products_context = await search_products(
                        user_query="",
                        quiz_json=quiz_json_obj,
                        allowed_magazine_ids=current_magazine.id,
                        top_k=10
                    )
                elif feed_url == "PREMIUM_AGGREGATOR":
                    products_context = await search_products(
                        user_query="",
                        quiz_json=quiz_json_obj,
                        allowed_magazine_ids=TOP_SHOPS_IDS,
                        top_k=10
                    )
                else:
                    final_shop_url = current_magazine.url_website
                    logger.warning(f"⚠️ У магазина '{current_magazine.name}' нет YML. Поиск по сайту: {final_shop_url}")
            else:
                products_context = await search_products(
                    user_query="",
                    quiz_json=quiz_json_obj,
                    allowed_magazine_ids=TOP_SHOPS_IDS,
                    top_k=10
                )

            # --- ГЕНЕРАЦИЯ ОТВЕТА (долгая операция) ---
            system_prompt = get_system_prompt(
                mode="catalog_mode",
                quiz_data=quiz_data_str,
                shop_url=final_shop_url,
                products_context=products_context
            )

            answer = await ask_responses_api(
                user_message="Подбери мне подходящую коляску",
                system_instruction=system_prompt
            )

            # --- ФУТЕР ---
            if first_catalog_request:
                answer += get_marketing_footer("catalog_mode")

            # --- УДАЛЯЕМ СООБЩЕНИЕ "Анализирую..." ---
            with contextlib.suppress(Exception):
                await bot.delete_message(chat_id=chat_id, message_id=typing_msg_id)

            # --- ОТПРАВКА ОТВЕТА ---
            try:
                await bot.send_message(chat_id, answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            except Exception:
                await bot.send_message(chat_id, answer, parse_mode=None, disable_web_page_preview=True)

            # --- СОХРАНЕНИЕ В БД (только флаги, запрос уже списан атомарно в хэндлере) ---
            await update_user_flags(session, telegram_id, closed_menu_flag=False, first_catalog_request=False)

    except Exception as e:
        logger.error(f"Error in _run_auto_request_task: {e}", exc_info=True)
        # Возвращаем запрос — он был списан авансом, но LLM не ответил
        await refund_request(telegram_id)
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=typing_msg_id)
        with contextlib.suppress(Exception):
            await bot.send_message(chat_id, "⚠️ Произошла ошибка на сервере. Запрос не списан, попробуйте ещё раз.")
    finally:
        stop_event.set()
        typing_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typing_task


@for_user_router.callback_query(F.data == "first_request")
async def process_first_auto_request(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    # === 1. FSM-БЛОКИРОВКА ОТ ДВОЙНОГО КЛИКА ===
    current_state = await state.get_state()
    if current_state == AIChat.catalog_mode.state:
        # Если юзер уже нажал кнопку и ждет — показываем всплывающее уведомление
        await call.answer("⏳ Пожалуйста, подождите. Я уже ищу для вас коляску!", show_alert=True)
        return

    # Переключаем режим (ставим FSM-блокировку)
    await state.set_state(AIChat.catalog_mode)
    await call.answer()

    # === 2. УДАЛЕНИЕ КНОПКИ ИЗ ИНТЕРФЕЙСА (UX) ===
    try:
        # Убираем клавиатуру (кнопку), но оставляем сам текст сообщения
        await call.message.edit_reply_markup(reply_markup=None)

        # Или, если хотите удалить сообщение с кнопкой целиком, раскомментируйте строку ниже:
        # await call.message.delete()
    except Exception as e:
        pass  # Игнорируем ошибку, если сообщение уже удалено/изменено

    # === 3. ПОЛУЧЕНИЕ ЮЗЕРА ===
    user = await get_user_cached(session, call.from_user.id)
    if not user:
        await state.clear()  # Снимаем блокировку
        return

    # === 4. SQL-БЛОКИРОВКА (Резервирование баланса) ===
    reserved = await try_reserve_request(session, call.from_user.id)
    if not reserved:
        await state.clear()  # Снимаем блокировку
        await call.message.answer(
            f"💡 Чтобы я мог выдать точный результат и завершить персональный анализ под ваши условия, выберите "
            f"пакет запросов ниже\n\n"
            f"<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
            f"(Как это работает и что считается запросом?)</a>",
            reply_markup=kb.pay
        )
        return

    # === 5. ИНДИКАЦИЯ И ЗАПУСК ЗАДАЧИ ===
    typing_msg = await call.message.answer("🔍 Анализирую ваши ответы из квиза и ищу лучшее решение...")

    # Запускаем тяжёлую работу в фоне — не ждём её завершения
    asyncio.create_task(
        _run_auto_request_task(
            bot=bot,
            chat_id=call.message.chat.id,
            telegram_id=call.from_user.id,
            typing_msg_id=typing_msg.message_id,
            user_id=user.id,
            magazine_id=user.magazine_id,
            first_catalog_request=user.first_catalog_request,
        )
    )
#⚠️⚠️⚠️⚠️⚠️⚠️ Восстановить если код выше хуйня
# @for_user_router.callback_query(F.data == "first_request")
# async def process_first_auto_request(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
#     await call.answer()
#     # Переключаем режим сразу на "Каталог"
#     await state.set_state(AIChat.catalog_mode)
#
#     # Получаем юзера через кэш Redis
#     user = await get_user_cached(session, call.from_user.id)
#     if not user:
#         return
#
#     # Атомарно резервируем запрос в БД.
#     # WHERE requests_left > 0 гарантирует: даже при 10 одновременных кликах
#     # только один пройдёт, остальные получат False.
#     reserved = await try_reserve_request(session, call.from_user.id)
#     if not reserved:
#         await call.message.answer(
#             f"💡 Чтобы я мог выдать точный результат и завершить персональный анализ под ваши условия, выберите "
#             f"пакет запросов ниже"
#             f"\n\n<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
#             "(Как это работает и что считается запросом?)</a>",
#             reply_markup=kb.pay
#         )
#         return
#
#     # Отправляем индикацию — хэндлер на этом заканчивается, Telegram получает 200 OK
#     typing_msg = await call.message.answer("🔍 Анализирую ваши ответы из квиза и ищу лучшее решение...")
#
#     # Запускаем тяжёлую работу в фоне — не ждём её завершения
#     asyncio.create_task(
#         _run_auto_request_task(
#             bot=bot,
#             chat_id=call.message.chat.id,
#             telegram_id=call.from_user.id,
#             typing_msg_id=typing_msg.message_id,
#             user_id=user.id,
#             magazine_id=user.magazine_id,
#             first_catalog_request=user.first_catalog_request,
#         )
#     )






# @for_user_router.callback_query(F.data == "first_request")
# async def process_first_auto_request(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
#     await call.answer()
#     # 2. Переключаем режим сразу на "Каталог"
#     await state.set_state(AIChat.catalog_mode)
#
#     # 3. Получаем юзера
#     # Молниеносные запросы в БД через кэш Redis (что бы снять нагрузку из-за частых, однотипных обращений в БД)
#     user = await get_user_cached(session, call.from_user.id)
#     if not user: return
#
#     # Проверка лимитов
#     if user.requests_left <= 0:
#         await call.message.answer(  # Исправил message.answer на call.message.answer
#             f"💡 Чтобы я мог выдать точный результат и завершить персональный анализ под ваши условия, выберите "
#             f"пакет запросов ниже"
#             f"\n\n<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
#             "(Как это работает и что считается запросом?)</a>",
#             reply_markup=kb.pay
#         )
#         return
#
#     # 4. Визуальная индикация работы
#     typing_msg = await call.message.answer("🔍 Анализирую ваши ответы из квиза и ищу лучшее решение...")
#
#     # Запускаем "печатание"
#     stop_event = asyncio.Event()
#     typing_task = asyncio.create_task(send_typing(bot, call.message.chat.id, stop_event))
#
#     try:
#         # --- СБОР ДАННЫХ ---
#         mag_result = await session.execute(select(Magazine).where(Magazine.id == user.magazine_id))
#         current_magazine = mag_result.scalar_one_or_none()
#
#         # Достаем ответы на квиз
#         quiz_data_str = "Нет данных."
#         quiz_json_obj = {}
#         user_branch = "pregnant"
#
#         quiz_result = await session.execute(
#             select(UserQuizProfile).where(UserQuizProfile.user_id == user.id).order_by(UserQuizProfile.id.desc()).limit(
#                 1)
#         )
#         quiz_profile = quiz_result.scalar_one_or_none()
#
#         if quiz_profile:
#             if quiz_profile.branch:
#                 user_branch = quiz_profile.branch
#             try:
#                 if isinstance(quiz_profile.data, str):
#                     quiz_json_obj = json.loads(quiz_profile.data)
#                     quiz_data_str = quiz_profile.data
#                 else:
#                     quiz_json_obj = quiz_profile.data
#                     quiz_data_str = json.dumps(quiz_profile.data, ensure_ascii=False)
#             except:
#                 pass
#
#         # --- ПОИСК В БАЗЕ (ОБНОВЛЕННАЯ ЛОГИКА) ---
#         products_context = ""
#         final_shop_url = None
#
#         if current_magazine:
#             feed_url = current_magazine.feed_url
#
#             # Условие 1: Если есть конкретная ссылка на YML (Обычный магазин)
#             if feed_url and "http" in feed_url:
#                 products_context = await search_products(
#                     user_query="",  # <--- ПУСТОЙ ЗАПРОС (только квиз)
#                     quiz_json=quiz_json_obj,
#                     allowed_magazine_ids=current_magazine.id,  # Ищем только у него
#                     top_k=10
#                 )
#
#             # Условие 3: Если это "Технический магазин" для платных (поиск по ТОП-5)
#             # В базе у такого магазина в feed_url должно быть написано "PREMIUM_AGGREGATOR"
#             elif feed_url == "PREMIUM_AGGREGATOR":
#                 products_context = await search_products(
#                     user_query="",
#                     quiz_json=quiz_json_obj,
#                     allowed_magazine_ids=TOP_SHOPS_IDS,  # 🔥 Ищем по списку ТОП-5
#                     top_k=10
#                 )
#
#             # Условие 2: Если feed_url пустой -> Векторный поиск отключен
#             else:
#                 final_shop_url = current_magazine.url_website
#                 # print для логов, чтобы видеть, что сработала ветка Гугла
#                 print(f"⚠️ У магазина '{current_magazine.name}' нет YML. Используем поиск по сайту: {final_shop_url}")
#
#         else:
#             # Fallback: Если магазин вообще не привязан -> Ищем по ТОП-5
#             products_context = await search_products(
#                 user_query="",
#                 quiz_json=quiz_json_obj,
#                 allowed_magazine_ids=TOP_SHOPS_IDS,
#                 top_k=10
#             )
#
#         # --- ГЕНЕРАЦИЯ ОТВЕТА ---
#         system_prompt = get_system_prompt(
#             mode="catalog_mode",
#             quiz_data=quiz_data_str,
#             shop_url=final_shop_url,  # Если заполнился (Условие 2), AI будет знать, куда идти
#             products_context=products_context
#         )
#
#         fake_user_message = "Подбери мне подходящую коляску"
#
#         answer = await ask_responses_api(
#             user_message=fake_user_message,
#             system_instruction=system_prompt
#         )
#
#         # --- ФУТЕР (Маркетинг) ---
#         if user.first_catalog_request:
#             marketing_footer = get_marketing_footer("catalog_mode")
#             answer += marketing_footer
#             user.first_catalog_request = False  # Сжигаем только его
#
#         # --- ОТПРАВКА ---
#         await typing_msg.delete()
#
#         try:
#             await call.message.answer(answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
#         except Exception:
#             await call.message.answer(answer, parse_mode=None, disable_web_page_preview=True)
#
#         # Списываем запрос и снимаем флаг для доступа к меню
#         # --- 🔥 ФИНАЛЬНОЕ СОХРАНЕНИЕ (Используем сервисы) ---
#         # 1. Списываем запрос (обновит БД и Кэш)
#         await update_user_requests(session, user.telegram_id, decrement=1)
#         # 2. Обновляем флаг closed_menu_flag и first_catalog_request
#         await update_user_flags(session, user.telegram_id, closed_menu_flag=False, first_catalog_request=False)
#
#     except Exception as e:
#         logger.error(f"Error in auto-request: {e}", exc_info=True)
#         await call.message.answer("⚠️ Произошла ошибка на сервере. Нажмите кнопку еще раз.")
#     finally:
#         stop_event.set()
#         typing_task.cancel()
#         await state.clear()



# ==========================================
# 1. ОБРАБОТКА КНОПОК (ВЫБОР РЕЖИМА)
# ==========================================
@for_user_router.callback_query(F.data.in_({"mode_catalog", "mode_info"}))
async def process_mode_selection(callback: CallbackQuery, state: FSMContext):
    mode = callback.data

    if mode == "mode_catalog":
        await state.set_state(AIChat.catalog_mode)
        text = (
            "👶 Режим: Подбор коляски"
            "\n\nОпишите, какую коляску вы ищете (например: 'Легкая для самолета' или "
            "'Вездеход для зимы')")
    else:
        await state.set_state(AIChat.info_mode)
        text = ("❓ Режим: Вопрос эксперту"
                "\n\nЗадайте любой вопрос (например: 'Что лучше: Anex или Tutis?' или "
                "'Как смазать колеса?')")

    await callback.message.edit_text(text)
    await callback.answer()


# ==========================================
# 2. ОБРАБОТКА ТЕКСТА (С УЧЕТОМ РЕЖИМА)
# ==========================================
async def _run_ai_message_task(
    bot: Bot,
    chat_id: int,
    telegram_id: int,
    user_text: str,
    typing_msg_id: int,
    user_id: int,
    magazine_id,
    is_catalog_mode: bool,
    first_catalog_request: bool,
    first_info_request: bool,
):
    """
    Фоновая задача для обработки текстового запроса к AI.
    Запускается через asyncio.create_task — хэндлер не ждёт её завершения,
    Telegram сразу получает 200 OK.
    Использует собственную сессию БД.
    """
    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(send_typing(bot, chat_id, stop_event))

    try:
        async with session_maker() as session:
            # --- СБОР ДАННЫХ О МАГАЗИНЕ ---
            mag_result = await session.execute(select(Magazine).where(Magazine.id == magazine_id))
            current_magazine = mag_result.scalar_one_or_none()

            quiz_data_str = "Нет данных."
            quiz_json_obj = {}

            quiz_result = await session.execute(
                select(UserQuizProfile)
                .where(UserQuizProfile.user_id == user_id)
                .order_by(UserQuizProfile.id.desc())
                .limit(1)
            )
            quiz_profile = quiz_result.scalar_one_or_none()

            if quiz_profile:
                try:
                    if isinstance(quiz_profile.data, str):
                        quiz_json_obj = json.loads(quiz_profile.data)
                        quiz_data_str = quiz_profile.data
                    else:
                        quiz_json_obj = quiz_profile.data
                        quiz_data_str = json.dumps(quiz_profile.data, ensure_ascii=False)
                except Exception:
                    pass

            # --- ЛОГИКА ПОИСКА (ТОЛЬКО ДЛЯ CATALOG MODE) ---
            products_context = ""
            final_shop_url = None

            if is_catalog_mode:
                if current_magazine:
                    feed_url = current_magazine.feed_url

                    if feed_url and "http" in feed_url:
                        products_context = await search_products(
                            user_query=user_text,
                            quiz_json=quiz_json_obj,
                            allowed_magazine_ids=current_magazine.id,
                            top_k=10
                        )
                    elif feed_url == "PREMIUM_AGGREGATOR":
                        products_context = await search_products(
                            user_query=user_text,
                            quiz_json=quiz_json_obj,
                            allowed_magazine_ids=TOP_SHOPS_IDS,
                            top_k=10
                        )
                    else:
                        final_shop_url = current_magazine.url_website
                else:
                    products_context = await search_products(
                        user_query=user_text,
                        quiz_json=quiz_json_obj,
                        allowed_magazine_ids=TOP_SHOPS_IDS,
                        top_k=10
                    )

            # --- ГЕНЕРАЦИЯ (долгая операция) ---
            mode_key = "catalog_mode" if is_catalog_mode else "info_mode"

            system_prompt = get_system_prompt(
                mode=mode_key,
                quiz_data=quiz_data_str,
                shop_url=final_shop_url,
                products_context=products_context
            )

            answer = await ask_responses_api(
                user_message=user_text,
                system_instruction=system_prompt
            )

            # --- ФУТЕРЫ ---
            marketing_footer = ""
            if is_catalog_mode:
                if first_catalog_request:
                    marketing_footer = get_marketing_footer("catalog_mode")
                    await update_user_flags(session, telegram_id, first_catalog_request=False)
            else:
                if first_info_request:
                    marketing_footer = get_marketing_footer("info_mode")
                    await update_user_flags(session, telegram_id, first_info_request=False)

            if marketing_footer:
                answer += marketing_footer

            # --- УДАЛЯЕМ "Думаю..." ---
            with contextlib.suppress(Exception):
                await bot.delete_message(chat_id=chat_id, message_id=typing_msg_id)

            # --- ОТПРАВКА ---
            try:
                await bot.send_message(chat_id, answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            except TelegramBadRequest as e:
                logger.error(f"HTML Parse Error: {e}")
                await bot.send_message(chat_id, answer, parse_mode=None, disable_web_page_preview=True)

            # --- СПИСАНИЕ УЖЕ ВЫПОЛНЕНО АТОМАРНО В ХЭНДЛЕРЕ ---
            # update_user_requests здесь не нужен

    except Exception as e:
        logger.error(f"Error in _run_ai_message_task: {e}", exc_info=True)
        # Возвращаем запрос — он был списан авансом, но LLM не ответил
        await refund_request(telegram_id)
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=typing_msg_id)
        with contextlib.suppress(Exception):
            await bot.send_message(chat_id, "⚠️ Произошла ошибка. Запрос не списан, попробуйте ещё раз.")
    finally:
        stop_event.set()
        typing_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typing_task


# ==========================================
# 2. ОБРАБОТКА ТЕКСТА (С УЧЕТОМ РЕЖИМА)
# ==========================================
@for_user_router.message(F.text, AIChat.catalog_mode)
@for_user_router.message(F.text, AIChat.info_mode)
async def handle_ai_message(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    # Проверки (промокод, баланс...)
    if await closed_menu(message=message, session=session):
        return

    # Атомарно резервируем запрос в БД.
    # WHERE requests_left > 0 гарантирует защиту от быстрых повторных нажатий.
    reserved = await try_reserve_request(session, message.from_user.id)
    if not reserved:
        await message.answer(
            f"💡 Чтобы я мог выдать точный результат и завершить персональный анализ под ваши условия, выберите "
            f"пакет запросов ниже"
            f"\n\n<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
            "(Как это работает и что считается запросом?)</a>",
            reply_markup=kb.pay
        )
        return

    current_state = await state.get_state()
    is_catalog_mode = (current_state == AIChat.catalog_mode.state)

    # Получаем юзера через кэш Redis (нужны id, magazine_id, флаги)
    user = await get_user_cached(session, message.from_user.id)
    if not user:
        return

    # Отправляем индикацию — хэндлер на этом заканчивается, Telegram получает 200 OK
    typing_msg = await message.answer("🤔 Думаю..." if not is_catalog_mode else "🔍 Ищу варианты...")

    # Запускаем тяжёлую работу в фоне — не ждём её завершения
    asyncio.create_task(
        _run_ai_message_task(
            bot=bot,
            chat_id=message.chat.id,
            telegram_id=message.from_user.id,
            user_text=message.text,
            typing_msg_id=typing_msg.message_id,
            user_id=user.id,
            magazine_id=user.magazine_id,
            is_catalog_mode=is_catalog_mode,
            first_catalog_request=user.first_catalog_request,
            first_info_request=user.first_info_request,
        )
    )

# @for_user_router.message(F.text, AIChat.catalog_mode)
# @for_user_router.message(F.text, AIChat.info_mode)
# async def handle_ai_message(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
#     # Проверки (промокод, баланс...)
#     if await closed_menu(message=message, session=session): return
#
#     # Делаем "точечный" запрос в БД только за балансом
#     # Это гарантирует 100% точность, игнорируя старый кэш
#     result = await session.execute(
#         select(User.requests_left).where(User.telegram_id == message.from_user.id)
#     )
#     # Если база вернет None (маловероятно), подстрахуемся 0
#     real_balance = result.scalar_one_or_none() or 0
#
#     if real_balance <= 0:
#         await message.answer(
#             f"💡 Чтобы я мог выдать точный результат и завершить персональный анализ под ваши условия, выберите "
#             f"пакет запросов ниже"
#             f"\n\n<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
#             "(Как это работает и что считается запросом?)</a>",
#             reply_markup=kb.pay
#         )
#         return
#
#     # Получаем текущий режим (state)
#     current_state = await state.get_state()
#     is_catalog_mode = (current_state == AIChat.catalog_mode.state)
#
#     stop_event = asyncio.Event()
#     typing_task = asyncio.create_task(send_typing(bot, message.chat.id, stop_event))
#     typing_msg = await message.answer("🤔 Думаю..." if not is_catalog_mode else "🔍 Ищу варианты...")
#
#     try:
#         # Молниеносные запросы в БД через кэш Redis (что бы снять нагрузку из-за частых, однотипных обращений в БД)
#         user = await get_user_cached(session, message.from_user.id)
#         if not user: return
#         # --- СБОР ДАННЫХ ---
#         mag_result = await session.execute(select(Magazine).where(Magazine.id == user.magazine_id))
#         current_magazine = mag_result.scalar_one_or_none()
#
#         quiz_data_str = "Нет данных."
#         quiz_json_obj = {}
#         user_branch = "pregnant"  # Дефолт
#
#         quiz_result = await session.execute(
#             select(UserQuizProfile).where(UserQuizProfile.user_id == user.id).order_by(UserQuizProfile.id.desc()).limit(
#                 1)
#         )
#         quiz_profile = quiz_result.scalar_one_or_none()
#
#         if quiz_profile:
#             if quiz_profile.branch:
#                 user_branch = quiz_profile.branch
#             try:
#                 if isinstance(quiz_profile.data, str):
#                     quiz_json_obj = json.loads(quiz_profile.data)
#                     quiz_data_str = quiz_profile.data
#                 else:
#                     quiz_json_obj = quiz_profile.data
#                     quiz_data_str = json.dumps(quiz_profile.data, ensure_ascii=False)
#             except:
#                 pass
#
#         # --- ЛОГИКА ПОИСКА (ТОЛЬКО ДЛЯ CATALOG MODE) ---
#         products_context = ""
#         final_shop_url = None
#
#         if is_catalog_mode:
#             # Тут работает ChromaDB или Site Search (ОБНОВЛЕННАЯ ЛОГИКА)
#             if current_magazine:
#                 feed_url = current_magazine.feed_url
#
#                 # Условие 1: Конкретный YML
#                 if feed_url and "http" in feed_url:
#                     products_context = await search_products(
#                         user_query=message.text,  # Тут передаем текст пользователя
#                         quiz_json=quiz_json_obj,
#                         allowed_magazine_ids=current_magazine.id,
#                         top_k=10
#                     )
#
#                 # Условие 2: Премиум агрегатор (ТОП-5)
#                 elif feed_url == "PREMIUM_AGGREGATOR":
#                     products_context = await search_products(
#                         user_query=message.text,
#                         quiz_json=quiz_json_obj,
#                         allowed_magazine_ids=TOP_SHOPS_IDS,  # Поиск по списку топ магазинов
#                         top_k=10
#                     )
#
#                 # Условие 3: Пусто  -> Идем на сайт
#                 else:
#                     final_shop_url = current_magazine.url_website
#
#             else:
#                 # Fallback: Если магазина нет вообще -> Ищем по ТОП-5
#                 products_context = await search_products(
#                     user_query=message.text,
#                     quiz_json=quiz_json_obj,
#                     allowed_magazine_ids=TOP_SHOPS_IDS,
#                     top_k=10
#                 )
#
#         # Если режим INFO - мы просто пропускаем блок выше, products_context остается пустым,
#         # и get_system_prompt выдаст шаблон эксперта.
#
#         # --- ГЕНЕРАЦИЯ ---
#         mode_key = "catalog_mode" if is_catalog_mode else "info_mode"
#
#         system_prompt = get_system_prompt(
#             mode=mode_key,
#             quiz_data=quiz_data_str,
#             shop_url=final_shop_url,
#             products_context=products_context
#         )
#
#         answer = await ask_responses_api(
#             user_message=message.text,
#             system_instruction=system_prompt
#         )
#
#         # --- 🔥 НОВАЯ ЛОГИКА ФУТЕРОВ (ДВА ФЛАГА) ---
#         marketing_footer = ""
#
#         if is_catalog_mode:
#             # Если режим Каталога И это первый запрос в каталог
#             if user.first_catalog_request:
#                 marketing_footer = get_marketing_footer("catalog_mode")
#                 await update_user_flags(session, user.telegram_id, first_catalog_request=False)  # Сжигаем флаг каталога
#         else:
#             # Если режим Инфо И это первый запрос эксперту
#             if user.first_info_request:
#                 marketing_footer = get_marketing_footer("info_mode")
#                 await update_user_flags(session, user.telegram_id, first_info_request=False)  # Сжигаем флаг инфо
#
#         # Добавляем футер, если он сгенерировался
#         if marketing_footer:
#             answer += marketing_footer
#
#         # --- ОТПРАВКА ---
#         try:
#             await message.answer(answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
#         except TelegramBadRequest as e:
#             # Если даже HTML сломался (очень редко), логируем и шлем текст
#             logger.error(f"HTML Parse Error: {e}")
#             await message.answer(answer, parse_mode=None, disable_web_page_preview=True)
#
#         # 🔥 Вместо (списание запросов):
#         # Обновляем атомарно и БД, и Кэш
#         await update_user_requests(session, user.telegram_id, decrement=1)
#
#     except Exception as e:
#         logger.error(f"Error: {e}", exc_info=True)
#         await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
#     finally:
#         stop_event.set()
#         typing_task.cancel()
#         with contextlib.suppress(asyncio.CancelledError):
#             await typing_task
#         try:
#             await typing_msg.delete()
#         except:
#             pass



# ==========================================
# 4. ЛОВУШКА ДЛЯ ТЕКСТА БЕЗ РЕЖИМА
# ==========================================
@for_user_router.message(F.text)
async def handle_no_state(message: Message, bot:Bot, session: AsyncSession):
    """Если юзер пишет текст, но не выбрал кнопку -> показываем меню"""
    if await closed_menu(message=message, session=session):
        return

    # 🚀 Получаем данные мгновенно из Redis
    user = await get_user_cached(session, message.from_user.id)

    # 3. ЛОГИКА ПРОВЕРКИ
    if user.show_intro_message:
        # 🚀 Обновляем флаг через сервис (БД обновляется, кэш сбрасывается)
        await update_user_flags(session, user.telegram_id, show_intro_message=False)
        # 1. Пытаемся отправить мгновенно через Redis (PRO способ)
        # Мы ищем file_id, который сохранили под именем "ai_post"
        video_note_id = await redis_client.get("media:ai_post")

        if video_note_id:
            try:
                await message.answer_video_note(
                    video_note=video_note_id
                )
                await asyncio.sleep(1)
                await message.answer(
                    text="AI-консультант готов к работе!\n\n"
                         "Он умеет подбирать коляски, а также отвечать на любые вопросы по эксплуатации\n\n"
                         "👇 Выберите режим работы:"
                         "\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
                         "\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализа и "
                         "сравнения уже известных Вам моделей колясок",
                    reply_markup=kb.get_ai_mode_kb()
                )
                print(f"🔔 ПОПЫТКА 1 для AI: Redis)")
                return  # Успех, выходим
            except Exception as e:
                logger.error(f"Ошибка отправки video_note из Redis: {e}")

        # Отправляем "Красивое" сообщение (copy_message)
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=tech_channel_id,  # ID группы
                message_id=ai_post,  # ID сообщения из группы
            )
            await asyncio.sleep(1)
            await message.answer(
                text="AI-консультант готов к работе!\n\n"
                     "Он умеет подбирать коляски, а также отвечать на любые вопросы по эксплуатации\n\n"
                     "👇 Выберите режим работы:"
                     "\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
                     "\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализа и "
                     "сравнения уже известных Вам моделей колясок",
                reply_markup=kb.get_ai_mode_kb()
            )
        except TelegramBadRequest:
            # Получаем абсолютный путь к медиа-файлу
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            GIF_PATH = os.path.join(BASE_DIR, "..", "mediafile_for_bot", "video.mp4")
            gif_file = FSInputFile(GIF_PATH)
            # Отправляем медиа
            wait_msg = await message.answer_video(
                video=gif_file,
                caption="AI-консультант готов к работе!\n\n"
                        "Он умеет подбирать коляски, а также отвечать на любые вопросы по эксплуатации\n\n"
                        "👇 Выберите режим работы:"
                        "\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
                        "\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализа и "
                        "сравнения уже известных Вам моделей колясок",
                supports_streaming=True,
                reply_markup=kb.get_ai_mode_kb()
            )
    else:
        # Делаем "точечный" запрос в БД только за балансом
        # Это гарантирует 100% точность, игнорируя старый кэш
        result = await session.execute(
            select(User.requests_left).where(User.telegram_id == message.from_user.id)
        )
        # Если база вернет None (маловероятно), подстрахуемся 0
        real_balance = result.scalar_one_or_none() or 0
        await message.answer(
            f"👋 Чтобы я мог помочь, выберите, пожалуйста, режим работы:"
            f"\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
            f"\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализа и сравнения уже известных "
            f"Вам моделей колясок"
            f"\n\n<blockquote>Количество запросов\n"
            f"на вашем балансе: [ {real_balance} ]</blockquote>",
            reply_markup=kb.get_ai_mode_with_balance_kb()
        )


# Обработчик нажатия на кнопку "💳 Пополнить баланс ➕"
@for_user_router.callback_query(F.data == "top_up_balance")
async def process_top_up_balance_click(callback: CallbackQuery):
    # Обязательно отвечаем на callback, чтобы убрать часики загрузки
    await callback.answer()

    # Отправляем сообщение с оплатой
    await callback.message.answer(
        f"💡 Чтобы я мог выдать точный результат и завершить персональный анализ под ваши условия, выберите "
        f"пакет запросов ниже"
        f"\n\n<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
        "(Как это работает и что считается запросом?)</a>",
        reply_markup=kb.pay
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

    # 🆕 ОПРЕДЕЛЯЕМ EMAIL ДЛЯ ЧЕКА
    # Если у пользователя в БД есть email, берем его. Иначе — технический.
    receipt_email = user.email if user.email else "prokolyasky@yandex.ru"

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
                "email": receipt_email,
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
            disable_web_page_preview=True,
        )
        await callback.answer()

    except Exception:
        logger.exception("Ошибка при создании платежа")
        await callback.message.answer(
            "❌ Ошибка при создании платежа. Попробуйте позже."
        )



# Отправка сообщений/постов из каналов

@for_user_router.channel_post()
async def channel_post_handler(message: Message, bot: Bot) -> None:
    """
    Entry point для всех постов из каналов
    """

    # 1. Определяем: чей это канал и нужен ли он нам
    context = await resolve_channel_context(message)
    if context is None:
        return

    # 2. Проверяем — новый ли это пост (теперь передаем message.date)
    # 🔥 ИСПРАВЛЕНО: добавил message.date для проверки "свежести"
    if not await is_new_post(context, message.message_id, message.date):
        return

    # 3. Отправляем пост в диспетчер (он сам решит: кэшировать или рассылать)
    # 🔥 ИСПРАВЛЕНО: добавил передачу объекта bot
    await dispatch_post(
        context=context,
        message=message,
        bot=bot
    )





#Технический хендлер для определения id гифки
# @for_user_router.message()
# async def catch_animation(message: Message):
#     if message.animation:
#         await message.answer(
#             f"file_id:\n<code>{message.animation.file_id}</code>"
#         )
