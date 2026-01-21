import logging
import os  # Добавил для проверки ENV
from aiohttp import web
from decimal import Decimal

from app.payments.security_webhook_YooKassa import is_yookassa_ip, get_peer_ip
from app.db.config import session_maker
from app.db.crud import (
    get_payment_by_payment_id,
    mark_payment_succeeded,
    mark_payment_canceled,
    update_receipt_url,
    mark_payment_failed,
    increment_requests,
)
from app.payments.yookassa_client import fetch_payment

logger = logging.getLogger(__name__)


async def yookassa_webhook_handler(request: web.Request):
    bot = request.app["bot"]

    # 🛠 Для тестов через ngrok (если DEBUG=True в .env, то пропускаем проверку IP)
    # Убедись, что на проде DEBUG будет False или отсутствовать
    skip_ip_check = os.getenv("DEBUG") == "True"

    try:
        # Проверка IP (если не включен режим отладки)
        if not skip_ip_check:
            ip = get_peer_ip(request)
            if not ip or not is_yookassa_ip(ip):
                return web.Response(status=403, text="Forbidden IP")

        data = await request.json()

        event = data.get("event")
        obj = data.get("object", {})
        payment_id = obj.get("id")

        if not payment_id:
            return web.Response(text="no payment id")

        async with session_maker() as session:
            # 🔥 Открываем транзакцию. Она сама сделает commit в конце блока, если не будет ошибок.
            async with session.begin():

                payment = await get_payment_by_payment_id(session, payment_id)
                if not payment:
                    # Если платеж не найден (например, не создался pending), можно создать его тут или ответить 200
                    # Юкасса иногда шлет события очень быстро.
                    # Для надежности лучше ответить 200, но записать в лог.
                    logger.warning(f"Payment {payment_id} not found in DB")
                    return web.Response(text="payment not found locally")

                # ---------- ПРОВЕРКА ДУБЛЕЙ (Идемпотентность) ----------
                if payment.status == "succeeded":
                    return web.Response(text="already processed")

                # ---------- CANCELED ----------
                if event == "payment.canceled":
                    if payment.status != "canceled":
                        await mark_payment_canceled(session, payment_id)
                        # Сообщение можно отправить после транзакции или через create_task,
                        # но здесь это не критично
                        try:
                            await bot.send_message(payment.telegram_id, "❌ Платёж был отменён.")
                        except:
                            pass
                    return web.Response(text="canceled")

                # ---------- RECEIPT (Чек) ----------
                if event == "receipt.registration":
                    receipt_url = obj.get("registration_url")
                    if receipt_url and not payment.receipt_url:
                        await update_receipt_url(session, payment_id, receipt_url)
                    return web.Response(text="receipt updated")

                # ---------- SUCCEEDED ----------
                if event != "payment.succeeded":
                    return web.Response(text="ignored")

                # 🔐 ВЕРИФИКАЦИЯ ЧЕРЕЗ API ЮКАССЫ
                api_payment = await fetch_payment(payment_id)

                if api_payment["status"] != "succeeded":
                    await mark_payment_failed(session, payment_id)
                    await bot.send_message(payment.telegram_id, "❌ Оплата не прошла (статус API).")
                    return web.Response(text="failed")

                amount = Decimal(api_payment["amount"]["value"])
                if amount != payment.amount:
                    await mark_payment_failed(session, payment_id)
                    logger.error(f"Amount mismatch: DB {payment.amount} != API {amount}")
                    return web.Response(text="amount mismatch")

                # Пытаемся достать чек из ответа API (если он там есть сразу)
                receipt_url = (api_payment.get("receipt", {}) or {}).get("registration_url")

                # ---------- НАЧИСЛЕНИЕ (БИЗНЕС-ЛОГИКА) ----------
                if amount == Decimal("29.00"):  # Исправил на твои суммы из pay_config.py
                    await increment_requests(session, payment.telegram_id, 1)
                elif amount == Decimal("190.00"):
                    await increment_requests(session, payment.telegram_id, 10)
                elif amount == Decimal("950.00"):
                    await increment_requests(session, payment.telegram_id, 50)
                elif amount == Decimal("1900.00"):  # Полный доступ
                    await increment_requests(session, payment.telegram_id, 50)
                    # Добавь сюда логику активации полного доступа, если нужно

                # Обновляем статус платежа
                await mark_payment_succeeded(session, payment_id, receipt_url)

            # 🔥 Блок session.begin() закончился -> произошел COMMIT.
            # Если мы здесь, значит в базе всё сохранилось успешно.

        # ---------- УВЕДОМЛЕНИЕ ПОЛЬЗОВАТЕЛЯ ----------
        # Отправляем сообщение только если транзакция прошла
        text = "✅ <b>Оплата прошла успешно!</b>\nЗапросы начислены."
        if receipt_url:
            text += f"\n\n🧾 <a href='{receipt_url}'>Электронный чек</a>"

        try:
            await bot.send_message(payment.telegram_id, text)
        except Exception as e:
            logger.error(f"Failed to send success message: {e}")

        return web.Response(text="ok")

    except Exception:
        logger.exception("YooKassa webhook failed")
        return web.Response(status=500, text="internal error")