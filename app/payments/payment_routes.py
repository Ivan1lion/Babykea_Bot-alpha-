import logging


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

    try:
        data = await request.json()

        event = data.get("event")
        obj = data.get("object", {})
        payment_id = obj.get("id")

        if not payment_id:
            return web.Response(text="no payment id")

        async with session_maker() as session:
            async with session.begin():

                payment = await get_payment_by_payment_id(session, payment_id)
                if not payment:
                    # webhook пришёл раньше создания pending
                    return web.Response(text="payment not registered yet")

                # ---------- CANCELED ----------
                if event == "payment.canceled":
                    if payment.status != "canceled":
                        await mark_payment_canceled(session, payment_id)
                        await bot.send_message(
                            payment.telegram_id,
                            "❌ Платёж был отменён.",
                        )
                    return web.Response(text="canceled")

                # ---------- RECEIPT ----------
                if event == "receipt.registration":
                    receipt_url = obj.get("registration_url")
                    if receipt_url and not payment.receipt_url:
                        await update_receipt_url(session, payment_id, receipt_url)
                    return web.Response(text="receipt updated")

                # ---------- SUCCEEDED ----------
                if event != "payment.succeeded":
                    return web.Response(text="ignored")

                if payment.status == "succeeded":
                    return web.Response(text="already processed")

                # 🔐 ВЕРИФИКАЦИЯ ЧЕРЕЗ API
                api_payment = await fetch_payment(payment_id)

                if api_payment["status"] != "succeeded":
                    await mark_payment_failed(session, payment_id)
                    await bot.send_message(
                        payment.telegram_id,
                        "❌ Оплата не прошла. Попробуйте ещё раз.",
                    )
                    return web.Response(text="failed")

                amount = Decimal(api_payment["amount"]["value"])
                if amount != payment.amount:
                    await mark_payment_failed(session, payment_id)
                    await bot.send_message(
                        payment.telegram_id,
                        "❌ Ошибка суммы платежа. Обратитесь в поддержку.",
                    )
                    return web.Response(text="amount mismatch")

                receipt_url = (
                    api_payment.get("receipt", {}) or {}
                ).get("registration_url")

                # ---------- БИЗНЕС-ЛОГИКА ----------
                if amount == Decimal("1.00"):
                    await increment_requests(session, payment.telegram_id, 1)
                elif amount == Decimal("190.00"):
                    await increment_requests(session, payment.telegram_id, 10)
                elif amount == Decimal("950.00"):
                    await increment_requests(session, payment.telegram_id, 50)
                elif amount == Decimal("2.00"):
                    await increment_requests(session, payment.telegram_id, 49)

                await mark_payment_succeeded(
                    session,
                    payment_id,
                    receipt_url,
                )

        # ---------- УВЕДОМЛЕНИЕ ПОСЛЕ COMMIT ----------
        text = "✅ Оплата прошла успешно!"
        if receipt_url:
            text += f"\n\n🧾 Чек: {receipt_url}"

        await bot.send_message(payment.telegram_id, text)

        return web.Response(text="ok")

    except web.HTTPException:
        raise
    except Exception:
        logger.exception("YooKassa webhook failed")
        return web.Response(status=500, text="internal error")