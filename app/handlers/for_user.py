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
from app.db.models import User, MagazineChannel, ChannelState, Magazine, Payment, UserQuizProfile
from app.db.config import session_maker
from app.posting.resolver import resolve_channel_context
from app.posting.state import is_new_post
from app.posting.dispatcher import dispatch_post
from app.openai_assistant.responses_client import ask_responses_api
from app.openai_assistant.prompts_config import get_system_prompt, get_marketing_footer
from app.payments.pay_config import PAYMENTS
from app.services.search_service import search_products
from app.services.user_service import get_user_cached, update_user_requests, update_user_flags
from app.redis_client import redis_client





logger = logging.getLogger(__name__)
for_user_router = Router()

# channel = int(os.getenv("CHANNEL_ID"))

class ActivationState(StatesGroup):
    waiting_for_promo_code = State()

class AIChat(StatesGroup):
    catalog_mode = State()  # Режим подбора (работает Pinecone / Feed)
    info_mode = State()     # Режим вопросов (работает Google Search / Общие знания)


# ID магазинов, по которым ищем для ПЛАТНЫХ пользователей
# 🔥🔥🔥🔥🔥🔥🔥🔥(Замени цифры на реальные ID твоих 5 крупных магазинов в БД)🔥🔥🔥🔥🔥🔥🔥🔥
TOP_SHOPS_IDS = [2]


# команд СТАРТ
@for_user_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, session: AsyncSession):
    await get_or_create_user(session, message.from_user.id, message.from_user.username)
    # 1. Пытаемся отправить мгновенно через Redis (PRO способ)
    # Мы ищем file_id, который сохранили под именем "intro_video"
    video_note_id = await redis_client.get("media:intro_video")

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
            from_chat_id=-1003498991864, # ID группы
            message_id=28,  # ID сообщения из группы
            reply_markup=kb.quiz_start
        )
        print(f"🔔 ПОПЫТКА 2: Пересылка из канала)")
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
        photo="https://i.postimg.cc/15Qn287s/Безымянный.jpg",
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

    if not magazine:
        await message.answer("⚠️ <b>Код не сработал</b>"
                             "\n\nЭто не вина магазина — Вам выдали действующий код, просто система иногда "
                             "может капризничать. Попробуйте ещё раз"
                             "\n\n<blockquote>Если опять не получится напишите мне @Master_PROkolyaski. Я лично проверю "
                             "ваш промокод и открою доступ к видео и советам вручную, чтобы вы могли "
                             "продолжить без лишних нервов</blockquote>"
                             )
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

    await session.commit()
    await state.clear()

    # Текст сообщения одинаковый, меняется только клавиатура
    success_text = (
        f'✅ Проведена успешная активация по промокоду магазина детских колясок "{magazine.name}"\n\n'
        f'Контакты продавца будут находиться в меню в разделе\n'
        f'"📍 Магазин колясок"'
    )

    # 4. Проверка условия branch
    if branch == 'service_only':
        await message.answer(text=success_text, reply_markup=kb.manual_mode)
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
@for_user_router.callback_query(F.data == "first_request")
async def process_first_auto_request(call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    await call.answer()
    # 2. Переключаем режим сразу на "Каталог"
    await state.set_state(AIChat.catalog_mode)

    # 3. Получаем юзера
    # Молниеносные запросы в БД через кэш Redis (что бы снять нагрузку из-за частых, однотипных обращений в БД)
    user = await get_user_cached(session, call.from_user.id)
    if not user: return

    # Проверка лимитов
    if user.requests_left <= 0:
        await call.message.answer(  # Исправил message.answer на call.message.answer
            f"💡 Чтобы я мог выдать точный результат и завершить персональный анализ под ваши условия, выберите "
            f"пакет запросов ниже"
            f"\n\n<a href='https://telegra.ph/AI-konsultant-rabotaet-na-platnoj-platforme-httpsplatformopenaicom-01-16'>"
            "(Как это работает и что считается запросом?)</a>",
            reply_markup=kb.pay
        )
        return

    # 4. Визуальная индикация работы
    typing_msg = await call.message.answer("🔍 Анализирую ваши ответы из квиза и ищу лучшее решение...")

    # Запускаем "печатание"
    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(send_typing(bot, call.message.chat.id, stop_event))

    try:
        # --- СБОР ДАННЫХ ---
        mag_result = await session.execute(select(Magazine).where(Magazine.id == user.magazine_id))
        current_magazine = mag_result.scalar_one_or_none()

        # Достаем ответы на квиз
        quiz_data_str = "Нет данных."
        quiz_json_obj = {}
        user_branch = "pregnant"

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

        # --- ПОИСК В БАЗЕ (ОБНОВЛЕННАЯ ЛОГИКА) ---
        products_context = ""
        final_shop_url = None

        if current_magazine:
            feed_url = current_magazine.feed_url

            # Условие 1: Если есть конкретная ссылка на YML (Обычный магазин)
            if feed_url and "http" in feed_url:
                products_context = await search_products(
                    user_query="",  # <--- ПУСТОЙ ЗАПРОС (только квиз)
                    quiz_json=quiz_json_obj,
                    allowed_magazine_ids=current_magazine.id,  # Ищем только у него
                    top_k=10
                )

            # Условие 3: Если это "Технический магазин" для платных (поиск по ТОП-5)
            # В базе у такого магазина в feed_url должно быть написано "PREMIUM_AGGREGATOR"
            elif feed_url == "PREMIUM_AGGREGATOR":
                products_context = await search_products(
                    user_query="",
                    quiz_json=quiz_json_obj,
                    allowed_magazine_ids=TOP_SHOPS_IDS,  # 🔥 Ищем по списку ТОП-5
                    top_k=10
                )

            # Условие 2: Если feed_url пустой (или "Google_Search") -> Векторный поиск отключен
            else:
                final_shop_url = current_magazine.url_website
                # print для логов, чтобы видеть, что сработала ветка Гугла
                print(f"⚠️ У магазина '{current_magazine.name}' нет YML. Используем поиск по сайту: {final_shop_url}")

        else:
            # Fallback: Если магазин вообще не привязан -> Ищем по ТОП-5
            products_context = await search_products(
                user_query="",
                quiz_json=quiz_json_obj,
                allowed_magazine_ids=TOP_SHOPS_IDS,
                top_k=10
            )

        # --- ГЕНЕРАЦИЯ ОТВЕТА ---
        system_prompt = get_system_prompt(
            mode="catalog_mode",
            quiz_data=quiz_data_str,
            shop_url=final_shop_url,  # Если заполнился (Условие 2), AI будет знать, куда идти
            products_context=products_context
        )

        fake_user_message = "Подбери мне подходящую коляску"

        answer = await ask_responses_api(
            user_message=fake_user_message,
            system_instruction=system_prompt
        )

        # --- ФУТЕР (Маркетинг) ---
        if user.first_catalog_request:
            marketing_footer = get_marketing_footer("catalog_mode")
            answer += marketing_footer
            user.first_catalog_request = False  # Сжигаем только его

        # --- ОТПРАВКА ---
        await typing_msg.delete()

        try:
            await call.message.answer(answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except Exception:
            await call.message.answer(answer, parse_mode=None, disable_web_page_preview=True)

        # Списываем запрос и снимаем флаг для доступа к меню
        # --- 🔥 ФИНАЛЬНОЕ СОХРАНЕНИЕ (Используем сервисы) ---
        # 1. Списываем запрос (обновит БД и Кэш)
        await update_user_requests(session, user.telegram_id, decrement=1)
        # 2. Обновляем флаг closed_menu_flag
        await update_user_flags(session, user.telegram_id, closed_menu_flag=False)

    except Exception as e:
        logger.error(f"Error in auto-request: {e}", exc_info=True)
        await call.message.answer("⚠️ Произошла ошибка на сервере. Нажмите кнопку еще раз.")
    finally:
        stop_event.set()
        typing_task.cancel()
        await state.clear()



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
@for_user_router.message(F.text, AIChat.catalog_mode)
@for_user_router.message(F.text, AIChat.info_mode)
async def handle_ai_message(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    # Проверки (промокод, баланс...)
    if await closed_menu(message=message, session=session): return

    # Молниеносные запросы в БД через кэш Redis (что бы снять нагрузку из-за частых, однотипных обращений в БД)
    user = await get_user_cached(session, message.from_user.id)
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
            # Тут работает ChromaDB или Site Search (ОБНОВЛЕННАЯ ЛОГИКА)
            if current_magazine:
                feed_url = current_magazine.feed_url

                # Условие 1: Конкретный YML
                if feed_url and "http" in feed_url:
                    products_context = await search_products(
                        user_query=message.text,  # Тут передаем текст пользователя
                        quiz_json=quiz_json_obj,
                        allowed_magazine_ids=current_magazine.id,
                        top_k=10
                    )

                # Условие 3: Премиум агрегатор (ТОП-5)
                elif feed_url == "PREMIUM_AGGREGATOR":
                    products_context = await search_products(
                        user_query=message.text,
                        quiz_json=quiz_json_obj,
                        allowed_magazine_ids=TOP_SHOPS_IDS,  # Поиск по списку топ магазинов
                        top_k=10
                    )

                # Условие 2: Пусто или Google_Search -> Идем на сайт
                else:
                    final_shop_url = current_magazine.url_website

            else:
                # Fallback: Если магазина нет вообще -> Ищем по ТОП-5
                products_context = await search_products(
                    user_query=message.text,
                    quiz_json=quiz_json_obj,
                    allowed_magazine_ids=TOP_SHOPS_IDS,
                    top_k=10
                )

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

        # --- 🔥 НОВАЯ ЛОГИКА ФУТЕРОВ (ДВА ФЛАГА) ---
        marketing_footer = ""

        if is_catalog_mode:
            # Если режим Каталога И это первый запрос в каталог
            if user.first_catalog_request:
                marketing_footer = get_marketing_footer("catalog_mode")
                await update_user_flags(session, user.telegram_id, first_catalog_request=False)  # Сжигаем флаг каталога
        else:
            # Если режим Инфо И это первый запрос эксперту
            if user.first_info_request:
                marketing_footer = get_marketing_footer("info_mode")
                await update_user_flags(session, user.telegram_id, first_info_request=False)  # Сжигаем флаг инфо

        # Добавляем футер, если он сгенерировался
        if marketing_footer:
            answer += marketing_footer

        # --- ОТПРАВКА ---
        try:
            await message.answer(answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except TelegramBadRequest as e:
            # Если даже HTML сломался (очень редко), логируем и шлем текст
            logger.error(f"HTML Parse Error: {e}")
            await message.answer(answer, parse_mode=None, disable_web_page_preview=True)

        # 🔥 Вместо (списание запросов):
        # user.requests_left -= 1
        # await session.commit()
        # Обновляем атомарно и БД, и Кэш
        await update_user_requests(session, user.telegram_id, decrement=1)

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
        # Мы ищем file_id, который сохранили под именем "intro_video"
        video_note_id = await redis_client.get("media:ai_intro")

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
                from_chat_id=-1003498991864,  # ID группы
                message_id=4,  # ID сообщения из группы
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
        # ИНАЧЕ -> Отправляем обычное сообщение
        await message.answer(
            f"👋 Чтобы я мог помочь, выберите, пожалуйста, режим работы:"
            f"\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
            f"\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализа и сравнения уже известных "
            f"Вам моделей колясок"
            f"\n\n<blockquote>Количество запросов\n"
            f"на вашем балансе: [ {user.requests_left} ]</blockquote>",
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
