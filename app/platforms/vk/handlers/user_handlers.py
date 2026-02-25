"""
VK-хэндлеры пользователя.

Аналог platforms/telegram/handlers/user_handlers.py, но для VK API.

Ключевые отличия от Telegram:
  - Нет /команд — используем текстовые кнопки и payload
  - Нет HTML-разметки — только plain text
  - Нет callback_query — есть message_event (для inline-кнопок)
  - Нет FSMContext — состояние храним в Redis
  - file_id не работает — для медиа нужны attachment строки (photo-123_456)
"""

import os
import json
import logging
import asyncio

from vkbottle import API
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import User, Magazine, UserQuizProfile
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

import app.platforms.vk.keyboards as vk_kb

logger = logging.getLogger(__name__)

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://bot.mastermanifest.ru")


# ============================================================
# MESSAGE_NEW — обработка текстовых сообщений
# ============================================================

async def handle_message_new(message: dict, vk_api: API, session_maker):
    """
    Обрабатывает входящее сообщение от VK-пользователя.

    message — dict из VK Callback API:
      {"id": ..., "from_id": 12345, "text": "Привет", "peer_id": 12345, ...}
    """
    vk_id = message.get("from_id")
    text = (message.get("text") or "").strip()
    peer_id = message.get("peer_id", vk_id)
    payload = _parse_payload(message)

    if not vk_id or vk_id < 0:
        return  # Сообщения от групп игнорируем

    async with session_maker() as session:
        # Получаем или создаём пользователя
        user = await get_or_create_user_vk(session, vk_id)

        # --- Обработка payload от кнопок ---
        if payload:
            cmd = payload.get("cmd", "")
            await _handle_command(cmd, vk_id, peer_id, user, session, vk_api, session_maker)
            return

        # --- Текстовые команды (от кнопок главного меню) ---
        text_lower = text.lower()

        if text_lower in ("начать", "start", "старт"):
            await _handle_start(vk_id, peer_id, user, session, vk_api)
            return

        if text_lower == "🤖 ai-консультант":
            await _handle_command("ai_consultant", vk_id, peer_id, user, session, vk_api, session_maker)
            return

        if text_lower == "📖 путеводитель":
            await _handle_command("guide", vk_id, peer_id, user, session, vk_api, session_maker)
            return

        if text_lower == "💢 правила":
            await _handle_command("rules", vk_id, peer_id, user, session, vk_api, session_maker)
            return

        if text_lower == "📍 магазин":
            await _handle_command("magazine", vk_id, peer_id, user, session, vk_api, session_maker)
            return

        if text_lower == "📝 блог":
            await _handle_command("blog", vk_id, peer_id, user, session, vk_api, session_maker)
            return

        if text_lower == "❓ помощь":
            await _handle_command("help", vk_id, peer_id, user, session, vk_api, session_maker)
            return

        # --- Свободный текст → AI-ассистент ---
        await _handle_ai_message(text, vk_id, peer_id, user, session, vk_api)


# ============================================================
# MESSAGE_EVENT — обработка нажатий inline-кнопок
# ============================================================

async def handle_message_event(event: dict, vk_api: API, session_maker):
    """
    Обрабатывает нажатие inline-кнопки (message_event).

    event — dict:
      {"user_id": 12345, "peer_id": 12345, "payload": {"cmd": "..."}, "event_id": "..."}
    """
    vk_id = event.get("user_id")
    peer_id = event.get("peer_id", vk_id)
    payload = event.get("payload", {})
    event_id = event.get("event_id")
    cmd = payload.get("cmd", "")

    if not vk_id:
        return

    # Подтверждаем событие (убирает спиннер с кнопки)
    try:
        await vk_api.messages.send_message_event_answer(
            event_id=event_id,
            user_id=vk_id,
            peer_id=peer_id,
        )
    except Exception:
        pass

    async with session_maker() as session:
        user = await get_or_create_user_vk(session, vk_id)
        await _handle_command(cmd, vk_id, peer_id, user, session, vk_api, session_maker)


# ============================================================
# РОУТЕР КОМАНД
# ============================================================

async def _handle_command(cmd, vk_id, peer_id, user, session, vk_api, session_maker=None):
    """Центральный роутер команд из payload кнопок."""

    if cmd == "kb_activation":
        await _handle_start(vk_id, peer_id, user, session, vk_api)

    elif cmd == "pay_access":
        await _handle_payment(vk_id, peer_id, "pay_access", session, vk_api)

    elif cmd == "enter_promo":
        # Устанавливаем состояние ожидания промокода в Redis
        await redis_client.set(f"vk_state:{vk_id}", "waiting_promo", ex=300)
        await _send(vk_api, peer_id, "Введите промокод:")

    elif cmd in ("pay29", "pay190", "pay950"):
        await _handle_payment(vk_id, peer_id, cmd, session, vk_api)

    elif cmd == "top_up_balance":
        await _send(vk_api, peer_id, "Выберите тариф:", keyboard=vk_kb.pay_kb())

    elif cmd == "first_request":
        await _handle_ai_auto_request(vk_id, peer_id, user, session, vk_api)

    elif cmd == "rules_mode":
        await _handle_rules(vk_id, peer_id, vk_api)

    elif cmd == "ai_consultant":
        await _handle_ai_menu(vk_id, peer_id, user, vk_api)

    elif cmd in ("mode_catalog", "mode_info"):
        mode = "catalog" if cmd == "mode_catalog" else "info"
        await redis_client.set(f"vk_ai_mode:{vk_id}", mode, ex=3600)
        prompt = "Подобрать коляску" if mode == "catalog" else "Свободный вопрос"
        await _send(vk_api, peer_id, f"Режим: {prompt}\n\nВведите ваш вопрос:")

    elif cmd == "guide":
        await _send(vk_api, peer_id, "📖 Путеводитель: функция в разработке для VK")

    elif cmd == "rules":
        await _handle_rules(vk_id, peer_id, vk_api)

    elif cmd == "magazine":
        await _send(vk_api, peer_id, "📍 Магазин: функция в разработке для VK")

    elif cmd == "blog":
        await _send(vk_api, peer_id, "📝 Блог: функция в разработке для VK")

    elif cmd == "help":
        await _send(vk_api, peer_id,
                    "❓ Помощь\n\n"
                    "Я — бот-консультант по детским коляскам.\n\n"
                    "Напишите мне вопрос, и я помогу подобрать коляску "
                    "или отвечу на ваш вопрос с помощью AI.")

    elif cmd.startswith("quiz:"):
        await _send(vk_api, peer_id, "Квиз: функция в разработке для VK")


# ============================================================
# ОСНОВНЫЕ ФУНКЦИИ
# ============================================================

async def _handle_start(vk_id, peer_id, user, session, vk_api):
    """Приветствие — аналог /start в Telegram."""
    await _send(
        vk_api, peer_id,
        "👋 Привет! Я — Babykea Bot\n\n"
        "🔍 Помогу подобрать коляску под ваши задачи (AI-подбор + видеорекомендации)\n"
        "🛠 Покажу, что делать после покупки и чего делать НЕЛЬЗЯ\n\n"
        "Используйте кнопки меню ниже 👇",
        keyboard=vk_kb.main_menu_kb(),
    )


async def _handle_ai_menu(vk_id, peer_id, user, vk_api):
    """Показываем меню AI-консультанта."""
    requests_left = user.requests_left if user else 0

    if requests_left > 0:
        text = f"🤖 AI-консультант\n\nУ вас {requests_left} запросов\n\nВыберите режим:"
        kb = vk_kb.ai_mode_kb()
    else:
        text = "🤖 AI-консультант\n\nУ вас 0 запросов.\n\nПополните баланс или выберите режим:"
        kb = vk_kb.ai_mode_with_balance_kb()

    await _send(vk_api, peer_id, text, keyboard=kb)


async def _handle_ai_message(text, vk_id, peer_id, user, session, vk_api):
    """Обработка свободного текстового сообщения → AI."""
    if not text:
        return

    # Проверяем состояние (ожидание промокода?)
    state = await redis_client.get(f"vk_state:{vk_id}")
    if state == "waiting_promo":
        await redis_client.delete(f"vk_state:{vk_id}")
        await _handle_promo_code(text, vk_id, peer_id, user, session, vk_api)
        return

    # Проверяем баланс
    reserved = await try_reserve_request(session, vk_id, platform="vk")
    if not reserved:
        await _send(
            vk_api, peer_id,
            "У вас закончились запросы к AI.\n\nПополните баланс:",
            keyboard=vk_kb.pay_kb(),
        )
        return

    # Определяем режим AI
    mode = await redis_client.get(f"vk_ai_mode:{vk_id}")
    if not mode:
        mode = "info"

    # Формируем промпт
    system_prompt = get_system_prompt(mode=mode)
    marketing_footer = get_marketing_footer(user)

    # Поиск по каталогу (если режим catalog)
    product_context = ""
    if mode == "catalog":
        products = await search_products(text, n_results=3)
        if products:
            product_context = "\n\n--- Найденные товары ---\n" + products

    full_prompt = f"{system_prompt}{product_context}\n\nВопрос пользователя: {text}"

    try:
        answer = await ask_responses_api(full_prompt)
        if marketing_footer:
            answer += f"\n\n{marketing_footer}"
    except Exception as e:
        logger.error(f"AI error for VK user {vk_id}: {e}")
        await refund_request(session, vk_id, platform="vk")
        await _send(vk_api, peer_id, "❌ Ошибка AI. Попробуйте ещё раз. Запрос не списан.")
        return

    await _send(vk_api, peer_id, answer)


async def _handle_ai_auto_request(vk_id, peer_id, user, session, vk_api):
    """Автоматический первый запрос (аналог first_request в TG)."""
    await _send(vk_api, peer_id, "🔄 Подбираю коляску на основе вашего профиля...")
    # TODO: Реализовать логику на основе UserQuizProfile
    await _send(vk_api, peer_id, "Функция автоподбора в разработке для VK. Напишите ваш вопрос вручную:")


async def _handle_rules(vk_id, peer_id, vk_api):
    """Правила эксплуатации."""
    await _send(
        vk_api, peer_id,
        "💢 Как НЕ сломать коляску\n\n"
        "Основные правила эксплуатации:\n\n"
        "1. Не складывайте коляску с установленным люком\n"
        "2. Не оставляйте на солнце — пластик деформируется\n"
        "3. Регулярно смазывайте колёса и шарниры\n"
        "4. Не превышайте допустимую нагрузку\n\n"
        "Подробнее — в разделе 📖 Путеводитель"
    )


async def _handle_payment(vk_id, peer_id, payment_type, session, vk_api):
    """Создание платёжной сессии и отправка ссылки на лендинг."""
    cfg = PAYMENTS.get(payment_type)
    if not cfg:
        await _send(vk_api, peer_id, "❌ Неизвестный тариф")
        return

    ps = await create_payment_session(
        session=session,
        vk_id=vk_id,
        payment_type=payment_type,
        platform="vk",
    )

    if not ps:
        await _send(vk_api, peer_id, "❌ Ошибка создания платежа. Попробуйте позже.")
        return

    checkout_url = f"{WEBHOOK_HOST}/checkout/{ps.token}"

    # Формируем текст без HTML (VK не поддерживает)
    text = cfg["description"] + f"\nСумма: {cfg['amount']} ₽"

    await _send(
        vk_api, peer_id,
        text,
        keyboard=vk_kb.payment_button_kb(checkout_url),
    )


async def _handle_promo_code(code, vk_id, peer_id, user, session, vk_api):
    """Обработка ввода промокода."""
    code = code.strip().upper()

    result = await session.execute(
        select(Magazine).where(Magazine.promo_code == code)
    )
    magazine = result.scalar_one_or_none()

    if not magazine:
        await _send(vk_api, peer_id, "❌ Промокод не найден. Попробуйте ещё раз:")
        await redis_client.set(f"vk_state:{vk_id}", "waiting_promo", ex=300)
        return

    # Привязываем магазин
    user.magazine_id = magazine.id
    user.promo_code = code
    await session.commit()

    await _send(
        vk_api, peer_id,
        f"✅ Промокод принят!\nМагазин: {magazine.name or 'Партнёр'}",
        keyboard=vk_kb.main_menu_kb(),
    )


# ============================================================
# УТИЛИТЫ
# ============================================================

async def _send(vk_api: API, peer_id: int, text: str, keyboard: str = None):
    """Отправка сообщения через VK API."""
    import random
    try:
        await vk_api.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=random.randint(1, 2**31),
            keyboard=keyboard,
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
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    except (json.JSONDecodeError, TypeError):
        return None
