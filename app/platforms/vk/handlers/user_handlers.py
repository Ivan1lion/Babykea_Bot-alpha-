"""
VK-хэндлеры пользователя — полный порт Telegram-логики.

Ключевые отличия от Telegram:
  - Нет /команд — используем текстовые кнопки (main_menu) и payload
  - Нет HTML-разметки — plain text (VK не парсит HTML в messages.send)
  - Нет callback_query — есть message_event (для inline-кнопок)
  - Нет FSMContext — состояние храним в Redis (vk_state:{vk_id})
  - Нет video_note (кружочки) — шлём ссылки на видео
  - Нет copy_message — контент собираем вручную
"""

import os
import json
import logging
import asyncio
import random
import contextlib

from vkbottle import API
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import User, Magazine, UserQuizProfile
from app.core.db.config import session_maker
from app.core.db.crud import get_or_create_user_vk
from app.core.openai_assistant.responses_client import ask_responses_api
from app.core.openai_assistant.prompts_config import get_system_prompt, get_marketing_footer
from app.core.services.pay_config import PAYMENTS
from app.core.services.search_service import search_products
from app.core.services.user_service import (
    get_user_cached,
    update_user_requests,
    update_user_flags,
    try_reserve_request,
    refund_request,
)
from app.core.services.payment_service import create_payment_session
from app.core.redis_client import redis_client
from app.core.quiz.quiz_state_service import (
    get_or_create_quiz_profile,
    get_current_step,
    validate_next,
    save_and_next,
    go_back,
)
from app.core.quiz.config_quiz import QUIZ_CONFIG

import app.platforms.vk.keyboards as vk_kb

logger = logging.getLogger(__name__)

webhook_host = os.getenv("WEBHOOK_HOST", "https://bot.babykea.ru")
MY_USERNAME = os.getenv("MASTER_USERNAME", "Master_PROkolyaski")

# ID магазинов для ПЛАТНЫХ пользователей (тот же список что в TG)
TOP_SHOPS_IDS = [2]


# ============================================================
# MESSAGE_NEW — обработка текстовых сообщений
# ============================================================

async def handle_message_new(message: dict, vk_api: API, sm):
    """Обрабатывает входящее сообщение от VK-пользователя."""
    vk_id = message.get("from_id")
    text = (message.get("text") or "").strip()
    peer_id = message.get("peer_id", vk_id)
    payload = _parse_payload(message)

    if not vk_id or vk_id < 0:
        return  # Сообщения от групп игнорируем

    async with sm() as session:
        user = await get_or_create_user_vk(session, vk_id)

        # --- Обработка payload от кнопок ---
        if payload:
            cmd = payload.get("cmd") or payload.get("command", "")
            # VK системная кнопка «Начать» шлёт {"command": "start"}
            if cmd == "start":
                await _handle_start(vk_id, peer_id, user, session, vk_api)
                return
            await _handle_command(cmd, vk_id, peer_id, user, session, vk_api, sm)
            return

        # --- Проверяем состояние из Redis (FSM-замена) ---
        state = await redis_client.get(f"vk_state:{vk_id}")

        if state == "waiting_promo":
            await redis_client.delete(f"vk_state:{vk_id}")
            await _handle_promo_code(text, vk_id, peer_id, user, session, vk_api)
            return

        if state == "waiting_stroller_model":
            await redis_client.delete(f"vk_state:{vk_id}")
            await _handle_stroller_model(text, vk_id, peer_id, session, vk_api)
            return

        if state == "waiting_email":
            await redis_client.delete(f"vk_state:{vk_id}")
            await _handle_email_input(text, vk_id, peer_id, session, vk_api)
            return

        if state == "waiting_master_text":
            await redis_client.delete(f"vk_state:{vk_id}")
            await _handle_master_text(text, vk_id, peer_id, vk_api)
            return

        # --- Текстовые команды (от кнопок главного меню) ---
        text_lower = text.lower()

        if text_lower in ("начать", "start", "старт"):
            await _handle_start(vk_id, peer_id, user, session, vk_api)
            return

        # Кнопки главного меню
        menu_map = {
            "🤖 ai-консультант": "ai_consultant",
            "📖 путеводитель": "guide",
            "💢 правила": "rules",
            "✅ памятка": "manual",
            "📍 магазин": "contacts",
            "📝 блог": "blog",
            "❓ помощь": "help",
            "👤 профиль": "config",
        }

        for btn_text, cmd in menu_map.items():
            if text_lower == btn_text:
                await _handle_command(cmd, vk_id, peer_id, user, session, vk_api, sm)
                return

        # --- Проверяем AI-режим ---
        ai_mode = await redis_client.get(f"vk_ai_mode:{vk_id}")
        if ai_mode:
            await _handle_ai_message(text, vk_id, peer_id, user, session, vk_api, ai_mode, sm)
            return

        # --- Свободный текст без режима → показываем меню AI ---
        await _handle_no_state_text(text, vk_id, peer_id, user, session, vk_api)


# ============================================================
# MESSAGE_EVENT — обработка нажатий inline-кнопок
# ============================================================

async def handle_message_event(event: dict, vk_api: API, sm):
    """Обрабатывает нажатие inline-кнопки (message_event)."""
    vk_id = event.get("user_id")
    peer_id = event.get("peer_id", vk_id)
    payload = event.get("payload", {})
    event_id = event.get("event_id")
    cmd = payload.get("cmd", "")

    if not vk_id:
        return

    # Подтверждаем событие (убирает спиннер с кнопки)
    with contextlib.suppress(Exception):
        await vk_api.messages.send_message_event_answer(
            event_id=event_id, user_id=vk_id, peer_id=peer_id,
        )

    async with sm() as session:
        user = await get_or_create_user_vk(session, vk_id)
        await _handle_command(cmd, vk_id, peer_id, user, session, vk_api, sm)


# ============================================================
# ЦЕНТРАЛЬНЫЙ РОУТЕР КОМАНД
# ============================================================

async def _handle_command(cmd, vk_id, peer_id, user, session, vk_api, sm=None):
    """Маршрутизация команд из payload кнопок и текстового меню."""

    # === Старт / Активация ===
    if cmd == "kb_activation":
        await _handle_activation(vk_id, peer_id, vk_api)

    elif cmd == "pay_access":
        await _handle_payment(vk_id, peer_id, "pay_access", session, vk_api)

    elif cmd == "enter_promo":
        await redis_client.set(f"vk_state:{vk_id}", "waiting_promo", ex=300)
        await _send(vk_api, peer_id, "Введите код активации текстом:")

    # === Оплата ===
    elif cmd in ("pay29", "pay190", "pay950"):
        await _handle_payment(vk_id, peer_id, cmd, session, vk_api)

    elif cmd == "top_up_balance":
        await _send(vk_api, peer_id, "Выберите тариф:", keyboard=vk_kb.pay_kb())

    # === AI ===
    elif cmd == "ai_consultant":
        await _handle_ai_menu(vk_id, peer_id, user, session, vk_api)

    elif cmd == "first_request":
        await _handle_first_auto_request(vk_id, peer_id, user, session, vk_api, sm)

    elif cmd in ("mode_catalog", "mode_info"):
        mode = "catalog" if cmd == "mode_catalog" else "info"
        await redis_client.set(f"vk_ai_mode:{vk_id}", mode, ex=3600)
        if mode == "catalog":
            await _send(vk_api, peer_id,
                        "👶 Режим: Подбор коляски\n\n"
                        "Опишите, какую коляску вы ищете (например: «Легкая для самолета» "
                        "или «Вездеход для зимы»)")
        else:
            await _send(vk_api, peer_id,
                        "❓ Режим: Вопрос эксперту\n\n"
                        "Задайте любой вопрос (например: «Что лучше: Anex или Tutis?» "
                        "или «Как смазать колеса?»)")

    # === Инфо-команды ===
    elif cmd == "guide":
        await _handle_guide(vk_id, peer_id, user, session, vk_api)

    elif cmd == "rules":
        await _handle_rules(vk_id, peer_id, user, session, vk_api)

    elif cmd == "manual":
        await _handle_manual(vk_id, peer_id, user, session, vk_api)

    elif cmd == "rules_mode":
        await _handle_rules(vk_id, peer_id, user, session, vk_api)

    elif cmd == "next_service":
        await _handle_pamyatka(vk_id, peer_id, vk_api)

    elif cmd == "get_wb_link":
        await _handle_wb_link(vk_id, peer_id, session, vk_api)

    # === Профиль / Настройки ===
    elif cmd == "config":
        await _handle_config(vk_id, peer_id, user, session, vk_api)

    elif cmd == "contacts":
        await _handle_contacts(vk_id, peer_id, session, vk_api)

    elif cmd == "blog":
        await _handle_blog(vk_id, peer_id, session, vk_api)

    elif cmd == "toggle_blog_sub":
        await _handle_toggle_blog_sub(vk_id, peer_id, session, vk_api)

    elif cmd == "help":
        await _handle_help(vk_id, peer_id, vk_api)

    elif cmd == "contact_master":
        await _handle_contact_master(vk_id, peer_id, session, vk_api)

    elif cmd == "promo":
        await _handle_promo(vk_id, peer_id, session, vk_api)

    elif cmd == "email":
        await redis_client.set(f"vk_state:{vk_id}", "waiting_email", ex=300)
        await _send(vk_api, peer_id,
                    "📧 Укажите ваш Email для получения чеков.\n\n"
                    "Отправьте адрес электронной почты в ответном сообщении:")

    elif cmd == "service":
        await redis_client.set(f"vk_state:{vk_id}", "waiting_stroller_model", ex=300)
        await _send(vk_api, peer_id,
                    "🛠 Запись на плановое ТО\n\n"
                    "Пожалуйста, напишите марку и модель вашей коляски одним сообщением "
                    "(например: Tutis Uno 3+, Cybex Priam или Anex m/type)")

    elif cmd == "offer":
        await _handle_offer(vk_id, peer_id, vk_api)

    elif cmd == "quiz_restart":
        await _handle_quiz_restart(vk_id, peer_id, session, vk_api)

    elif cmd == "master26":
        await _handle_master_start(vk_id, peer_id, vk_api)

    elif cmd == "mf_start":
        await redis_client.set(f"vk_state:{vk_id}", "waiting_master_text", ex=600)
        await _send(vk_api, peer_id,
                    "👀 Жду вашу историю!\n\n"
                    "Опишите ситуацию во всех подробностях: что случилось, в чем сомнения "
                    "или чем хотите поделиться.\n\n"
                    "Напишите всё одним сообщением и отправляйте:")

    # === Квиз ===
    elif cmd == "quiz:start":
        await _handle_quiz_start(vk_id, peer_id, session, vk_api)

    elif cmd and cmd.startswith("quiz:select:"):
        option = cmd.split(":")[2]
        await _handle_quiz_select(vk_id, peer_id, option, session, vk_api)

    elif cmd == "quiz:next":
        await _handle_quiz_next(vk_id, peer_id, session, vk_api)

    elif cmd == "quiz:back":
        await _handle_quiz_back(vk_id, peer_id, session, vk_api)

    elif cmd == "quiz:restore":
        await _handle_quiz_start(vk_id, peer_id, session, vk_api)

    # === FAQ ===
    elif cmd in ("faq_1", "faq_2", "faq_3", "faq_4"):
        await _handle_faq(cmd, vk_id, peer_id, vk_api)

    elif cmd == "ai_info":
        await redis_client.set(f"vk_ai_mode:{vk_id}", "info", ex=3600)
        await _send(vk_api, peer_id,
                    "❓ Режим: Вопрос эксперту\n\n"
                    "Я готов отвечать! Задайте любой вопрос по эксплуатации, "
                    "ремонту или сравнению колясок")


# ============================================================
# ОСНОВНЫЕ ФУНКЦИИ
# ============================================================

# async def _handle_start(vk_id, peer_id, user, session, vk_api):
#     """Приветствие — аналог /start."""
#     await _send(
#         vk_api, peer_id,
#         "👋 Привет! Я — Babykea Bot\n\n"
#         "🔍 Помогу подобрать коляску под ваши задачи (AI-подбор + видеорекомендации)\n"
#         "🛠 Покажу, что делать после покупки и чего делать НЕЛЬЗЯ\n\n"
#         "Для начала пройдите короткий квиз-опрос 👇",
#         keyboard=vk_kb.quiz_start_kb(),
#     )
async def _handle_start(vk_id, peer_id, user, session, vk_api):
    """Приветствие — аналог /start (только видео + кнопка)."""
    await _send(
        vk_api,
        peer_id,
        "",  # Пустая строка, так как текст нам не нужен
        attachment="video-236264711_456239020",  # Базовый ID + ключ доступа
        keyboard=vk_kb.quiz_start_kb(),
    )


async def _handle_activation(vk_id, peer_id, vk_api):
    """Экран активации: оплата или промокод."""
    await _send(
        vk_api, peer_id,
        "Оплатите полный доступ ко всем разделам за 1900₽\n"
        "(В пакет также включены 50 бесплатных запросов к AI-консультанту)\n\n"
        "🎫 Есть флаер от магазина-партнера? — нажмите «Ввести код активации» "
        "для свободного доступа к моим личным видеорекомендациям и реальным советам",
        keyboard=vk_kb.activation_kb(),
    )


async def _handle_ai_menu(vk_id, peer_id, user, session, vk_api):
    """Меню AI-консультанта."""
    # Получаем актуальный баланс из БД
    result = await session.execute(
        select(User.requests_left).where(User.vk_id == vk_id)
    )
    real_balance = result.scalar_one_or_none() or 0

    if real_balance > 0:
        text = (f"🤖 AI-консультант\n\nУ вас {real_balance} запросов\n\n"
                "👇 Выберите режим работы:\n\n"
                "[Подобрать коляску] - поиск подходящей коляски\n\n"
                "[Другой запрос] - консультации, сравнения, эксплуатация")
        kb = vk_kb.ai_mode_kb()
    else:
        text = ("🤖 AI-консультант\n\nУ вас 0 запросов.\n\n"
                "Выберите режим работы или пополните баланс:\n\n"
                "[Подобрать коляску] - поиск подходящей коляски\n\n"
                "[Другой запрос] - консультации, сравнения, эксплуатация")
        kb = vk_kb.ai_mode_with_balance_kb()

    await _send(vk_api, peer_id, text, keyboard=kb)


async def _handle_no_state_text(text, vk_id, peer_id, user, session, vk_api):
    """Юзер пишет текст без выбранного режима → показываем меню."""
    user_cached = await get_user_cached(session, vk_id, platform="vk")

    if user_cached and user_cached.closed_menu_flag:
        await _send(vk_api, peer_id,
                    "⚠️ Для начала работы нужно пройти квиз-опрос и активировать доступ.",
                    keyboard=vk_kb.quiz_start_kb())
        return

    result = await session.execute(
        select(User.requests_left).where(User.vk_id == vk_id)
    )
    real_balance = result.scalar_one_or_none() or 0

    await _send(
        vk_api, peer_id,
        f"👋 Чтобы я мог помочь, выберите режим работы:\n\n"
        f"[Подобрать коляску] - поиск подходящей коляски\n\n"
        f"[Другой запрос] - консультации, сравнения, эксплуатация\n\n"
        f"Запросов на балансе: [ {real_balance} ]",
        keyboard=vk_kb.ai_mode_with_balance_kb(),
    )


# ============================================================
# AI — ОБРАБОТКА СООБЩЕНИЙ
# ============================================================

async def _handle_ai_message(text, vk_id, peer_id, user, session, vk_api, ai_mode, sm):
    """Обработка свободного текстового сообщения → AI."""
    if not text:
        return

    # Проверяем closed_menu
    user_cached = await get_user_cached(session, vk_id, platform="vk")
    if user_cached and user_cached.closed_menu_flag:
        await _send(vk_api, peer_id, "⚠️ Сначала активируйте доступ к боту.")
        return

    # Атомарно резервируем запрос
    reserved = await try_reserve_request(session, vk_id, platform="vk")
    if not reserved:
        await _send(
            vk_api, peer_id,
            "💡 Чтобы я мог выдать точный результат, выберите пакет запросов:",
            keyboard=vk_kb.pay_kb(),
        )
        return

    is_catalog = (ai_mode == "catalog")

    # Индикация
    await _send(vk_api, peer_id, "🔍 Ищу варианты..." if is_catalog else "🤔 Думаю...")

    # Запускаем AI в фоне
    asyncio.create_task(
        _run_ai_task(vk_api, peer_id, vk_id, text, is_catalog, user, sm)
    )


async def _run_ai_task(vk_api, peer_id, vk_id, user_text, is_catalog, user, sm):
    """Фоновая задача AI-ответа."""
    try:
        async with sm() as session:
            user_cached = await get_user_cached(session, vk_id, platform="vk")
            if not user_cached:
                return

            # Данные магазина
            mag_result = await session.execute(
                select(Magazine).where(Magazine.id == user_cached.magazine_id)
            )
            current_magazine = mag_result.scalar_one_or_none()

            # Данные квиза
            quiz_data_str = "Нет данных."
            quiz_json_obj = {}

            quiz_result = await session.execute(
                select(UserQuizProfile)
                .where(UserQuizProfile.user_id == user_cached.id)
                .order_by(UserQuizProfile.id.desc())
                .limit(1)
            )
            quiz_profile = quiz_result.scalar_one_or_none()
            if quiz_profile and quiz_profile.data:
                try:
                    quiz_json_obj = quiz_profile.data if isinstance(quiz_profile.data, dict) else json.loads(quiz_profile.data)
                    quiz_data_str = json.dumps(quiz_json_obj, ensure_ascii=False) if isinstance(quiz_profile.data, dict) else quiz_profile.data
                except Exception:
                    pass

            # Поиск (только catalog mode)
            products_context = ""
            final_shop_url = None

            if is_catalog:
                if current_magazine:
                    feed_url = current_magazine.feed_url
                    if feed_url and "http" in feed_url:
                        products_context = await search_products(
                            user_query=user_text, quiz_json=quiz_json_obj,
                            allowed_magazine_ids=current_magazine.id, top_k=10)
                    elif feed_url == "PREMIUM_AGGREGATOR":
                        products_context = await search_products(
                            user_query=user_text, quiz_json=quiz_json_obj,
                            allowed_magazine_ids=TOP_SHOPS_IDS, top_k=10)
                    else:
                        final_shop_url = current_magazine.url_website
                else:
                    products_context = await search_products(
                        user_query=user_text, quiz_json=quiz_json_obj,
                        allowed_magazine_ids=TOP_SHOPS_IDS, top_k=10)

            # Генерация ответа
            mode_key = "catalog_mode" if is_catalog else "info_mode"
            system_prompt = get_system_prompt(
                mode=mode_key, quiz_data=quiz_data_str,
                shop_url=final_shop_url, products_context=products_context)

            answer = await ask_responses_api(
                user_message=user_text, system_instruction=system_prompt)

            # Футеры
            if is_catalog and user_cached.first_catalog_request:
                answer += get_marketing_footer("catalog_mode")
                await update_user_flags(session, vk_id, platform="vk", first_catalog_request=False)
            elif not is_catalog and user_cached.first_info_request:
                answer += get_marketing_footer("info_mode")
                await update_user_flags(session, vk_id, platform="vk", first_info_request=False)

            # Убираем HTML-теги для VK
            answer = _strip_html(answer)
            await _send(vk_api, peer_id, answer)

    except Exception as e:
        logger.error(f"AI task error for VK:{vk_id}: {e}", exc_info=True)
        await refund_request(vk_id, platform="vk")
        await _send(vk_api, peer_id, "⚠️ Произошла ошибка. Запрос не списан, попробуйте ещё раз.")


async def _handle_first_auto_request(vk_id, peer_id, user, session, vk_api, sm):
    """Автоматический первый запрос «Подобрать коляску»."""
    reserved = await try_reserve_request(session, vk_id, platform="vk")
    if not reserved:
        await _send(
            vk_api, peer_id,
            "💡 Чтобы завершить анализ, выберите пакет запросов:",
            keyboard=vk_kb.pay_kb(),
        )
        return

    await _send(vk_api, peer_id, "🔍 Анализирую ваши ответы из квиза и ищу лучшее решение...")

    asyncio.create_task(
        _run_ai_task(vk_api, peer_id, vk_id, "Подбери мне подходящую коляску", True, user, sm)
    )


# ============================================================
# ИНФО-КОМАНДЫ
# ============================================================

async def _handle_guide(vk_id, peer_id, user, session, vk_api):
    """Аналог /guide."""
    text = (
        "📝 Шпаргалка: «Что нужно учитывать при подборе»\n\n"
        "1. Основа:\n"
        "• Тип коляски (от рождения или прогулка)\n"
        "• Функционал (2в1, 3в1 или просто люлька)\n"
        "• Формат использования (для прогулок или путешествий)\n"
        "• Сезон (зима или лето)\n"
        "• Тип дорог (грунт, асфальт или бездорожье)\n\n"
        "👆 Эти вопросы мы закрыли в квиз-опросе — это фундамент подбора\n\n"
        "2. Жизненные нюансы:\n"
        "• Ширина лифта (замерьте рулеткой!)\n"
        "• Глубина багажника авто\n"
        "• Ваш рост (высоким нужна рама с вынесенной осью)\n"
        "• Этажность и наличие лифта\n"
        "• Эргономика (капор, спинка, складывание)\n"
        "• Бюджет\n"
        "• Дизайн и цвет\n\n"
        "💡 Напишите свои условия AI-консультанту, например:\n"
        "«Живу на 5 этаже без лифта, узкие двери, муж высокий, бюджет 40к»\n\n"
        "Видео-версия:\n"
        "YouTube — https://www.youtube.com/\n"
        "RUTUBE — https://rutube.ru/\n"
        "VK Видео — https://vkvideo.ru/"
    )
    await _send(vk_api, peer_id, text)


async def _handle_rules(vk_id, peer_id, user, session, vk_api):
    """Аналог /rules."""
    text = (
        "💢 Как НЕ сломать коляску — видео:\n\n"
        "YouTube — https://www.youtube.com/\n"
        "RUTUBE — https://rutube.ru/\n"
        "VK Видео — https://vkvideo.ru/"
    )
    await _send(vk_api, peer_id, text)


async def _handle_manual(vk_id, peer_id, user, session, vk_api):
    """Аналог /manual."""
    text = (
        "✅ Как продлить жизнь коляске — видео:\n\n"
        "YouTube — https://www.youtube.com/\n"
        "RUTUBE — https://rutube.ru/\n"
        "VK Видео — https://vkvideo.ru/"
    )
    await _send(vk_api, peer_id, text, keyboard=vk_kb.next_service_kb())


async def _handle_pamyatka(vk_id, peer_id, vk_api):
    """Памятка — аналог next_service callback."""
    text = (
        "📌 Памятка: 3 способа как не убить коляску\n\n"
        "🚿 Никакого душа\n"
        "Не мойте колеса из шланга или в ванной. Вода вымоет смазку. Только влажная тряпка\n\n"
        "🏋️ Осторожнее с ручкой\n"
        "Не давите на неё всем весом перед бордюром — помогайте ногой, наступая на заднюю ось\n\n"
        "🛢 Забудьте про WD-40\n"
        "Вэдэшка сушит подшипники, бытовые масла притягивают песок. Только силиконовая смазка\n\n"
        "Если смазывать только коляску, флакона хватит на пару лет"
    )
    await _send(vk_api, peer_id, text, keyboard=vk_kb.get_wb_link_kb())


async def _handle_wb_link(vk_id, peer_id, session, vk_api):
    """Аналог get_wb_link callback."""
    from sqlalchemy.sql import func
    from sqlalchemy import update as sa_update

    # Аналитика
    stmt = select(User.wb_clicked_at).where(User.vk_id == vk_id)
    clicked_at = (await session.execute(stmt)).scalar_one_or_none()
    if clicked_at is None:
        await session.execute(
            sa_update(User).where(User.vk_id == vk_id).values(wb_clicked_at=func.now())
        )
        await session.commit()

    await _send(vk_api, peer_id,
                "Смазка силиконовая для колясок:\n"
                "https://www.wildberries.ru/catalog/191623733/detail.aspx?targetUrl=MI")


# ============================================================
# ПРОФИЛЬ / НАСТРОЙКИ
# ============================================================

async def _handle_config(vk_id, peer_id, user, session, vk_api):
    """Аналог /config."""
    text = (
        "👤 Мой профиль\n\n"
        "Выберите действие:"
    )
    await _send(vk_api, peer_id, text, keyboard=vk_kb.config_kb())


async def _handle_contacts(vk_id, peer_id, session, vk_api):
    """Аналог /contacts."""
    result = await session.execute(
        select(Magazine)
        .join(User, User.magazine_id == Magazine.id)
        .where(User.vk_id == vk_id)
    )
    magazine = result.scalar_one_or_none()

    if not magazine:
        await _send(vk_api, peer_id, "Магазин не найден")
        return

    if magazine.name == "[Babykea]":
        await _send(vk_api, peer_id,
                    "🏆 Магазины с высокой репутацией\n\n"
                    "• Первая-Коляска.РФ\n• Boan Baby\n• Lapsi\n• Кенгуру\n• Piccolo")
        return

    parts = [f"{magazine.name}\n",
             f"📍 Город: {magazine.city}",
             f"🏠 Адрес: {magazine.address}",
             f"🌐 Сайт: {magazine.url_website}"]
    if magazine.username_magazine:
        parts.append(f"💬 Telegram: {magazine.username_magazine}")

    text = "\n".join(parts)
    kb = vk_kb.magazine_map_kb(magazine.map_url) if magazine.map_url else None
    await _send(vk_api, peer_id, text, keyboard=kb)


async def _handle_blog(vk_id, peer_id, session, vk_api):
    """Аналог /blog."""
    text = (
        "📝 Блог мастера\n\n"
        "Мой канал: https://t.me/Ivan_PROkolyaski\n\n"
        "#мысливслух — информация к размышлению молодым родителям\n"
        "#маркетинговыеТефтели — маркетинговые уловки производителей колясок\n\n"
        "Подписывайтесь, чтобы не пропустить новые разборы и рекомендации"
    )
    await _send(vk_api, peer_id, text, keyboard=vk_kb.blog_kb())


async def _handle_toggle_blog_sub(vk_id, peer_id, session, vk_api):
    """Переключение подписки на рассылку."""
    stmt = select(User.subscribed_to_author).where(User.vk_id == vk_id)
    is_sub = (await session.execute(stmt)).scalar_one_or_none()
    if is_sub is None:
        is_sub = True

    new_status = not is_sub
    await session.execute(
        update(User).where(User.vk_id == vk_id).values(subscribed_to_author=new_status)
    )
    await session.commit()

    if new_status:
        await _send(vk_api, peer_id, "✅ Рассылка включена! Новые посты будут приходить в этот чат.")
    else:
        await _send(vk_api, peer_id, "🔕 Рассылка отключена. Технические напоминания сохранятся.")


async def _handle_help(vk_id, peer_id, vk_api):
    """Аналог /help."""
    text = (
        "🆘 Проблемы и решения\n\n"
        "1. Ответы на частые вопросы (нажмите кнопку):\n\n"
        "2. Умный помощник — AI-консультант с обширной базой знаний\n\n"
        "3. Связь с мастером — если бот не справился"
    )
    await _send(vk_api, peer_id, text, keyboard=vk_kb.help_kb())


async def _handle_faq(faq_cmd, vk_id, peer_id, vk_api):
    """FAQ видео-ответы."""
    faq_texts = {
        "faq_1": "«Новая коляска скрипит! Мне продали брак?»\n\nВ большинстве случаев скрип — это нормально для новых механизмов. Смажьте шарниры силиконовой смазкой.",
        "faq_2": "«Как снять колеса»\n\nЗависит от модели. Обычно нужно нажать кнопку на оси и потянуть колесо на себя.",
        "faq_3": "«Почему в люльке голова ниже ног?»\n\nПроверьте регулировку дна люльки. У большинства колясок есть регулятор наклона.",
        "faq_4": "«До скольки атмосфер качать колеса?»\n\nОбычно 1.5-2 атм. Точное значение указано на боковине покрышки.",
    }
    text = faq_texts.get(faq_cmd, "Информация недоступна")
    await _send(vk_api, peer_id, f"📹 {text}")


async def _handle_contact_master(vk_id, peer_id, session, vk_api):
    """Связь с мастером."""
    from app.core.db.models import Payment
    result = await session.execute(
        select(Payment).where(
            Payment.telegram_id == vk_id,  # TODO: изменить на vk_id lookup
            Payment.status == "succeeded"
        ).limit(1)
    )
    has_payment = result.scalar_one_or_none()

    if not has_payment:
        await _send(vk_api, peer_id,
                    "Лично отвечаю только на то, что не осилил AI-консультант.\n"
                    "Сначала спросите AI — в 90% случаев этого хватает.")
        return

    await _send(vk_api, peer_id,
                f"✅ Пришлите мне короткое видео (5-10 сек) и опишите суть вопроса.\n\n"
                f"Пишите мне в Telegram: @{MY_USERNAME}")


async def _handle_promo(vk_id, peer_id, session, vk_api):
    """Аналог /promo."""
    stmt = (
        select(Magazine.promo_code, Magazine.is_promo_active)
        .select_from(User)
        .join(Magazine)
        .where(User.vk_id == vk_id)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        await _send(vk_api, peer_id, "Сначала активируйте доступ к боту")
        return

    mag_promo, is_active = row
    if not is_active:
        await _send(vk_api, peer_id, "Срок действия вашего промокода истек")
        return

    bot_link = "https://t.me/babykea_bot"
    if mag_promo == "[BABYKEA_PREMIUM]":
        share_promo = "BKEA-4K7X"
        text = (f"👑 У вас PREMIUM-доступ!\n\n"
                f"Гостевой промокод для подруги: {share_promo}\n\n"
                f"Бот: {bot_link}")
    else:
        text = f"Ваш код активации: {mag_promo}\n\nМожете поделиться с друзьями!\n\nБот: {bot_link}"

    await _send(vk_api, peer_id, text)


async def _handle_offer(vk_id, peer_id, vk_api):
    """Аналог /offer."""
    await _send(vk_api, peer_id,
                "1. Публичная оферта:\n"
                "https://telegra.ph/PUBLICHNAYA-OFERTA-na-predostavlenie-prava-ispolzovaniya-"
                "funkcionala-Telegram-bota-Babykea-Bot-i-informacionnyh-materialov-02-23\n\n"
                "2. Политика Конфиденциальности:\n"
                "https://telegra.ph/POLITIKA-KONFIDENCIALNOSTI-polzovatelej-Telegram-bota-Babykea-"
                "Bot-02-23")


# ============================================================
# ОПЛАТА
# ============================================================

async def _handle_payment(vk_id, peer_id, payment_type, session, vk_api):
    """Создание платёжной сессии через лендинг (VK всегда через лендинг)."""
    cfg = PAYMENTS.get(payment_type)
    if not cfg:
        await _send(vk_api, peer_id, "❌ Неизвестный тариф")
        return

    ps = await create_payment_session(
        session=session, vk_id=vk_id,
        payment_type=payment_type, platform="vk",
    )
    if not ps:
        await _send(vk_api, peer_id, "❌ Ошибка создания платежа. Попробуйте позже.")
        return

    checkout_url = f"{WEBHOOK_HOST}/checkout/{ps.token}"
    text = f"{cfg['description']}\nСумма: {cfg['amount']} ₽"
    await _send(vk_api, peer_id, text, keyboard=vk_kb.payment_button_kb(checkout_url))


# ============================================================
# ПРОМОКОД
# ============================================================

async def _handle_promo_code(code, vk_id, peer_id, user, session, vk_api):
    """Обработка ввода промокода."""
    code = code.strip().upper()

    result = await session.execute(
        select(Magazine).where(Magazine.promo_code == code)
    )
    magazine = result.scalar_one_or_none()

    if not magazine:
        await _send(vk_api, peer_id,
                    "⚠️ Код не сработал\n\n"
                    "Попробуйте ещё раз. Если не получится — напишите @Master_PROkolyaski")
        await redis_client.set(f"vk_state:{vk_id}", "waiting_promo", ex=300)
        return

    if not magazine.is_promo_active:
        await _send(vk_api, peer_id, "У данного промокода истек срок активации.")
        return

    # Привязываем магазин
    user.promo_code = code
    user.magazine_id = magazine.id

    # Определяем branch
    quiz_result = await session.execute(
        select(UserQuizProfile.branch)
        .where(UserQuizProfile.user_id == user.id)
        .order_by(UserQuizProfile.id.desc())
        .limit(1)
    )
    branch = quiz_result.scalar_one_or_none()

    if branch == "service_only":
        user.closed_menu_flag = False

    await session.commit()
    await redis_client.delete(f"user:vk:{vk_id}")

    # Формируем ответ
    mag_name = magazine.name
    if mag_name and mag_name != "[Babykea]":
        success_text = (f"✅ Активация по промокоду магазина {mag_name}\n\n"
                        "Контакты продавца — в разделе «📍 Магазин»\n\n"
                        "Теперь проверим бота в деле 👇")
    else:
        success_text = ("✅ Код принят! Добро пожаловать\n\n"
                        "Давайте проверим бота в деле 👇")

    if branch == "service_only":
        await _send(vk_api, peer_id, success_text, keyboard=vk_kb.rules_mode_kb())
    else:
        await _send(vk_api, peer_id, success_text, keyboard=vk_kb.first_request_kb())


# ============================================================
# КВИЗ (текстовый — без фото, т.к. VK не поддерживает edit_message_media)
# ============================================================

async def _handle_quiz_start(vk_id, peer_id, session, vk_api):
    """Старт/рестарт квиза."""
    user = await get_or_create_user_vk(session, vk_id)
    profile = await get_or_create_quiz_profile(session, user)

    # Сбрасываем прогресс
    profile.branch = None
    profile.current_level = 1
    profile.completed = False
    profile.completed_once = False
    profile.data = {}
    session.add(profile)
    await session.commit()

    await _render_quiz_step_vk(vk_api, peer_id, profile)


async def _handle_quiz_select(vk_id, peer_id, option, session, vk_api):
    """Выбор варианта в квизе."""
    user = await get_or_create_user_vk(session, vk_id)
    profile = await get_or_create_quiz_profile(session, user)

    profile.data["_selected"] = option
    session.add(profile)
    await session.commit()

    await _render_quiz_step_vk(vk_api, peer_id, profile, selected=option)


async def _handle_quiz_next(vk_id, peer_id, session, vk_api):
    """Кнопка «Далее» в квизе."""
    user = await get_or_create_user_vk(session, vk_id)
    profile = await get_or_create_quiz_profile(session, user)

    step = get_current_step(profile)
    selected = profile.data.get("_selected")

    if not validate_next(selected):
        await _send(vk_api, peer_id, "⚠️ Выберите вариант, затем нажмите «Далее»")
        return

    await save_and_next(session=session, profile=profile, step=step, selected_option=selected)
    profile.data.pop("_selected", None)
    session.add(profile)
    await session.commit()

    if profile.completed:
        if profile.completed_once:
            await _send(vk_api, peer_id,
                        "✅ Квиз завершён\n\nВаши ответы обновлены.",
                        keyboard=vk_kb.ai_mode_kb())
            return

        profile.completed_once = True
        session.add(profile)
        await session.commit()

        await _send(
            vk_api, peer_id,
            "✅ Отлично! Квиз-опрос завершён\n\n"
            "Теперь у меня есть понимание ситуации. Данные помогут "
            "подбирать модели именно под ваши условия.\n\n"
            "Остался последний шаг — открыть доступ к подбору и рекомендациям",
            keyboard=vk_kb.activation_kb(),
        )
        return

    await _render_quiz_step_vk(vk_api, peer_id, profile)


async def _handle_quiz_back(vk_id, peer_id, session, vk_api):
    """Кнопка «Назад» в квизе."""
    user = await get_or_create_user_vk(session, vk_id)
    profile = await get_or_create_quiz_profile(session, user)
    await go_back(session, profile)
    await _render_quiz_step_vk(vk_api, peer_id, profile)


async def _handle_quiz_restart(vk_id, peer_id, session, vk_api):
    """Аналог /quiz_restart."""
    await _handle_quiz_start(vk_id, peer_id, session, vk_api)


async def _render_quiz_step_vk(vk_api, peer_id, profile, selected=None):
    """Рендерит шаг квиза для VK (текст + inline-кнопки)."""
    try:
        branch = profile.branch or "root"
        step = QUIZ_CONFIG[branch][profile.current_level]
    except KeyError:
        await _send(vk_api, peer_id, "❌ Ошибка квиза. Попробуйте заново.",
                    keyboard=vk_kb.quiz_start_kb())
        return

    text = step.get("text", "")
    keyboard = vk_kb.build_quiz_keyboard(step, profile, selected)
    await _send(vk_api, peer_id, text, keyboard=keyboard)


# ============================================================
# SERVICE / EMAIL / MASTER
# ============================================================

async def _handle_stroller_model(text, vk_id, peer_id, session, vk_api):
    """Запись модели коляски на ТО."""
    from datetime import datetime, timezone
    try:
        await session.execute(
            update(User).where(User.vk_id == vk_id).values(
                stroller_model=text,
                service_registered_at=datetime.now(timezone.utc),
                service_level=0,
            )
        )
        await session.commit()
    except Exception as e:
        logger.error(f"Service register error: {e}")
        await _send(vk_api, peer_id, "Ошибка при записи. Попробуйте позже.")
        return

    await _send(vk_api, peer_id,
                f"✅ Ваша коляска поставлена на учет!\n\n"
                f"Модель: {text}\n\n"
                "Уведомление придет, когда настанет время для ТО.")


async def _handle_email_input(text, vk_id, peer_id, session, vk_api):
    """Сохранение email."""
    import re
    email = text.strip().lower()

    if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
        await _send(vk_api, peer_id,
                    "❌ Некорректный формат email. Попробуйте ещё раз:")
        await redis_client.set(f"vk_state:{vk_id}", "waiting_email", ex=300)
        return

    await session.execute(
        update(User).where(User.vk_id == vk_id).values(email=email)
    )
    await session.commit()
    await _send(vk_api, peer_id, f"✅ Email сохранен: {email}")


async def _handle_master_start(vk_id, peer_id, vk_api):
    """Аналог /master26."""
    await _send(
        vk_api, peer_id,
        "📬 Код принят. Прямая линия открыта\n\n"
        "Сюда можно присылать вопросы по ремонту, муки выбора, "
        "истории удачных покупок или жалобы на магазины.\n\n"
        "Нажмите «Поделиться историей» чтобы начать:",
        keyboard=vk_kb.master_start_kb(),
    )


async def _handle_master_text(text, vk_id, peer_id, vk_api):
    """Приём текста обращения к мастеру."""
    # Пересылаем в канал через Telegram-бот (если доступен)
    # В VK-версии просто логируем
    logger.info(f"VK Master feedback from {vk_id}: {text[:200]}")
    await _send(vk_api, peer_id,
                "✅ Послание отправлено!\n\n"
                "Если это интересный случай — обсудим в канале! Спасибо 👍")


# ============================================================
# УТИЛИТЫ
# ============================================================

async def _send(vk_api: API, peer_id: int, text: str, keyboard: str = None, attachment: str = None):
    """Отправка сообщения через VK API."""
    try:
        # VK имеет лимит 4096 символов на сообщение
        if len(text) > 4000:
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, chunk in enumerate(chunks):
                await vk_api.messages.send(
                    peer_id=peer_id, message=chunk,
                    random_id=random.randint(1, 2 ** 31),
                    keyboard=keyboard if i == len(chunks) - 1 else None,
                    attachment=attachment if i == 0 else None,
                    dont_parse_links=1,
                )
        else:
            await vk_api.messages.send(
                peer_id=peer_id, message=text,
                random_id=random.randint(1, 2 ** 31),
                keyboard=keyboard, attachment=attachment,
                dont_parse_links=1,
            )
    except Exception as e:
        logger.error(f"VK send error to {peer_id}: {e}")


def _parse_payload(message: dict) -> dict | None:
    """Парсит payload из сообщения VK."""
    raw = message.get("payload")
    if not raw:
        return None
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None


def _strip_html(text: str) -> str:
    """Убирает HTML-теги из текста для VK."""
    import re
    # Заменяем <b>text</b> на text
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<blockquote>(.*?)</blockquote>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r"<a\s+href='([^']*)'[^>]*>(.*?)</a>", r'\2: \1', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    return text
