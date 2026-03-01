"""
Webhook-обработчик ЮKassa.
Мультиплатформенный: определяет откуда пришёл платёж и шлёт уведомление
через правильного бота (Telegram или VK).
"""

import logging
import os
from aiohttp import web
from decimal import Decimal

from app.web.security_webhook import is_yookassa_ip, get_peer_ip
from app.core.db.config import session_maker
from app.core.db.crud import (
    get_payment_by_payment_id,
    mark_payment_succeeded,
    mark_payment_canceled,
    update_receipt_url,
    mark_payment_failed,
    increment_requests,
    activate_premium_subscription,
)
from app.core.services.yookassa_client import fetch_payment

logger = logging.getLogger(__name__)


async def _notify_user(request: web.Request, platform: str, user_id: int, text: str):
    """
    Отправляет сообщение пользователю через правильную платформу.

    В request.app хранятся инстансы ботов:
      - request.app["bot"]    — Telegram Bot (aiogram)
      - request.app["vk_bot"] — VK Bot (vkbottle) [будет добавлен позже]
    """
    if platform == "vk":
        vk_bot = request.app.get("vk_bot")
        if vk_bot:
            try:
                await vk_bot.api.messages.send(
                    user_id=user_id,
                    message=text,  # VK не поддерживает HTML — чистый текст
                    random_id=0,
                )
            except Exception as e:
                logger.error(f"VK notification failed for {user_id}: {e}")
        else:
            logger.warning(f"VK bot not available, can't notify user {user_id}")
    else:
        # Telegram (по умолчанию)
        bot = request.app.get("bot")
        if bot:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logger.error(f"TG notification failed for {user_id}: {e}")


def _get_user_id(payment) -> int:
    """Возвращает ID пользователя в зависимости от платформы."""
    if payment.platform == "vk":
        return payment.vk_id
    return payment.telegram_id


async def yookassa_webhook_handler(request: web.Request):
    skip_ip_check = os.getenv("DEBUG") == "True"

    try:
        # 1. Проверка IP (безопасность)
        if not skip_ip_check:
            ip = get_peer_ip(request)
            if not ip or not is_yookassa_ip(ip):
                return web.Response(status=403, text="Forbidden IP")

        data = await request.json()
        event = data.get("event")
        obj = data.get("object", {})

        # Определяем ID (в чеке он называется payment_id, в платеже - id)
        if event == "receipt.registration":
            payment_id = obj.get("payment_id")
        else:
            payment_id = obj.get("id")

        if not payment_id:
            return web.Response(text="no payment id")

        # ---------------------------------------------------------------
        # ЛОГИКА ОБРАБОТКИ
        # ---------------------------------------------------------------
        async with session_maker() as session:
            async with session.begin():

                payment = await get_payment_by_payment_id(session, payment_id)
                if not payment:
                    logger.warning(f"Payment {payment_id} not found locally")
                    return web.Response(text="payment not found locally")

                platform = getattr(payment, "platform", "telegram")
                user_id = _get_user_id(payment)

                # === СЦЕНАРИЙ 1: ЧЕКА (receipt.registration) ===
                if event == "receipt.registration":
                    receipt_url = obj.get("registration_url")

                    if receipt_url and payment.receipt_url != receipt_url:
                        await update_receipt_url(session, payment_id, receipt_url)

                        await _notify_user(
                            request, platform, user_id,
                            f"🧾 Ваш чек готов:\n{receipt_url}"
                            if platform == "vk" else
                            f"🧾 <b>Ваш чек готов:</b>\n<a href='{receipt_url}'>Открыть чек</a>"
                        )

                    return web.Response(text="receipt updated")

                # === СЦЕНАРИЙ 2: УСПЕШНАЯ ОПЛАТА (payment.succeeded) ===
                if event == "payment.succeeded":

                    if payment.status == "succeeded":
                        return web.Response(text="already processed")

                    # Верификация через API
                    api_payment = await fetch_payment(payment_id)

                    if api_payment["status"] != "succeeded":
                        await mark_payment_failed(session, payment_id)
                        return web.Response(text="failed")

                    amount = Decimal(api_payment["amount"]["value"])

                    receipt_url = (api_payment.get("receipt", {}) or {}).get("registration_url")

                    # Начисление баланса
                    if amount == Decimal("1.00"):
                        await increment_requests(session, user_id, 1)
                    elif amount == Decimal("190.00"):
                        await increment_requests(session, user_id, 10)
                    elif amount == Decimal("950.00"):
                        await increment_requests(session, user_id, 50)
                    elif amount == Decimal("2.00"):
                        await activate_premium_subscription(session, user_id, 50)

                    await mark_payment_succeeded(session, payment_id, receipt_url)

                # === СЦЕНАРИЙ 3: ОТМЕНА ===
                elif event == "payment.canceled":
                    if payment.status != "canceled":
                        await mark_payment_canceled(session, payment_id)
                        await _notify_user(request, platform, user_id, "❌ Платёж был отменён.")
                    return web.Response(text="canceled")

                else:
                    return web.Response(text="ignored event")

        # ---------------------------------------------------------------
        # УВЕДОМЛЕНИЕ ПОЛЬЗОВАТЕЛЯ (payment.succeeded)
        # ---------------------------------------------------------------
        if event == "payment.succeeded":
            if amount == Decimal("2.00") or amount == Decimal("1900.00"):
                text_tg = ("🚀 <b>Полный доступ активирован!</b>"
                           "\n\nПерейдите в Меню для выбора подходящего действия")
                text_plain = "🚀 Полный доступ активирован!\n\nПерейдите в Меню для выбора подходящего действия"
            else:
                text_tg = ("✅ <b>Оплата прошла успешно!</b>"
                           "\n\nБаланс запросов к AI увеличен")
                text_plain = "✅ Оплата прошла успешно!\n\nБаланс запросов к AI увеличен"

            if receipt_url:
                text_tg += f"\n\n🧾 <a href='{receipt_url}'>Электронный чек</a>"
                text_plain += f"\n\n🧾 Чек: {receipt_url}"

            await _notify_user(
                request, platform, user_id,
                text_plain if platform == "vk" else text_tg
            )

            # После оплаты полного доступа — показываем главное меню (VK)
            if platform == "vk" and (amount == Decimal("2.00") or amount == Decimal("1900.00")):
                vk_bot = request.app.get("vk_bot")
                if vk_bot:
                    try:
                        import app.platforms.vk.keyboards as vk_kb
                        await vk_bot.api.messages.send(
                            user_id=user_id,
                            message="Чтобы свернуть 📋 Меню, нажмите на квадратик с 4 точками 👇",
                            keyboard=vk_kb.main_menu_kb(),
                            random_id=0,
                        )
                    except Exception as e:
                        logger.error(f"VK menu send failed for {user_id}: {e}")

        return web.Response(text="ok")

    except Exception as e:
        logger.exception(f"YooKassa webhook failed: {e}")
        return web.Response(status=500, text="internal error")