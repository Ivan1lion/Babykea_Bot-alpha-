import logging
import os
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
            async with session.begin():  # Одна транзакция

                payment = await get_payment_by_payment_id(session, payment_id)
                if not payment:
                    # Платеж не найден в базе (редкий кейс)
                    logger.warning(f"Payment {payment_id} not found locally")
                    return web.Response(text="payment not found locally")

                # === СЦЕНАРИЙ 1: ПРИШЕЛ ВЕБХУК О ЧЕКЕ (receipt.registration) ===
                # Если он придет — отлично, отправим юзеру. Если нет — код сюда просто не зайдет.
                if event == "receipt.registration":
                    receipt_url = obj.get("registration_url")

                    if receipt_url and payment.receipt_url != receipt_url:
                        await update_receipt_url(session, payment_id, receipt_url)

                        # Отправляем сообщение, только если URL реально есть
                        try:
                            await bot.send_message(
                                chat_id=payment.telegram_id,
                                text=f"🧾 <b>Ваш чек готов:</b>\n<a href='{receipt_url}'>Открыть чек</a>",
                                disable_web_page_preview=True
                            )
                        except Exception as e:
                            logger.error(f"Не удалось отправить чек пользователю {payment.telegram_id}: {e}")

                    return web.Response(text="receipt updated")

                # === СЦЕНАРИЙ 2: ПРИШЕЛ ВЕБХУК ОБ ОПЛАТЕ (payment.succeeded) ===
                if event == "payment.succeeded":

                    # Если уже обработан — выходим
                    if payment.status == "succeeded":
                        return web.Response(text="already processed")

                    # 1. Верификация через API (чтобы удостовериться в сумме и статусе)
                    api_payment = await fetch_payment(payment_id)

                    if api_payment["status"] != "succeeded":
                        await mark_payment_failed(session, payment_id)
                        return web.Response(text="failed")

                    amount = Decimal(api_payment["amount"]["value"])

                    # 2. Пытаемся достать чек СРАЗУ (если Юкасса успела его создать)
                    # Если чека нет — receipt_url будет None, и код не упадет.
                    receipt_url = (api_payment.get("receipt", {}) or {}).get("registration_url")

                    # 3. Начисление баланса
                    if amount == Decimal("1.00"):
                        await increment_requests(session, payment.telegram_id, 1)
                    elif amount == Decimal("190.00"):
                        await increment_requests(session, payment.telegram_id, 10)
                    elif amount == Decimal("950.00"):
                        await increment_requests(session, payment.telegram_id, 50)
                    elif amount == Decimal("2.00"):  # Тестовый полный доступ
                        await increment_requests(session, payment.telegram_id, 49)

                    # 4. Сохраняем успех и URL чека (если он есть) в базу
                    await mark_payment_succeeded(session, payment_id, receipt_url)

                # === СЦЕНАРИЙ 3: ОТМЕНА ===
                elif event == "payment.canceled":
                    if payment.status != "canceled":
                        await mark_payment_canceled(session, payment_id)
                        try:
                            await bot.send_message(payment.telegram_id, "❌ Платёж был отменён.")
                        except:
                            pass
                    return web.Response(text="canceled")

                else:
                    return web.Response(text="ignored event")

        # ---------------------------------------------------------------
        # УВЕДОМЛЕНИЕ ПОЛЬЗОВАТЕЛЯ (Только для payment.succeeded)
        # ---------------------------------------------------------------
        if event == "payment.succeeded":
            if amount == Decimal("2.00") or amount == Decimal("1900.00"):
                text = "🚀 <b>Полный доступ активирован!</b>"
            else:
                text = "✅ <b>Оплата прошла успешно!</b>\nЗапросы начислены."

            # ЛОГИКА "ЕСТЬ ЧЕК ИЛИ НЕТ":
            if receipt_url:
                # Если Юкасса сразу отдала ссылку — показываем
                text += f"\n\n🧾 <a href='{receipt_url}'>Электронный чек</a>"
            else:
                # Если ссылки нет — просто не пишем ничего про чек.
                # Пользователю не нужно знать про технические задержки.
                pass

            try:
                await bot.send_message(payment.telegram_id, text, disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Failed to send success message: {e}")

        return web.Response(text="ok")

    except Exception as e:
        logger.exception(f"YooKassa webhook failed: {e}")
        return web.Response(status=500, text="internal error")