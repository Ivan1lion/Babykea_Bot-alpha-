from aiohttp import web
from decimal import Decimal

from app.payments.security_webhook_YooKassa import is_yookassa_ip
from app.db.config import session_maker
from app.db.crud import increment_requests, get_payment, create_payment, send_receipt_async




async def yookassa_webhook_handler(request: web.Request):
    try:
        # peer_ip = request.remote
        # if not peer_ip or not is_yookassa_ip(peer_ip):
        #     return web.Response(status=403, text="Forbidden IP") пока выключаю потому что я не ИП

        data = await request.json()

        if data.get("event") != "payment.succeeded":
            return web.Response(status=200, text="Ignored event")

        payment = data["object"]
        if payment["status"] != "succeeded":
            return web.Response(status=200, text="Not succeeded")

        telegram_id = int(payment["metadata"]["telegram_id"])
        amount = Decimal(payment["amount"]["value"])
        payment_id = payment["id"]
        receipt_url = payment.get("receipt", {}).get("registration_url")

        async with session_maker() as session:
            async with session.begin():  # 🔹 одна транзакция на всю операцию
                existing = await get_payment(session, payment_id)
                if existing:
                    return web.Response(status=200, text="Already processed")

            await create_payment(session, payment_id, telegram_id, amount, receipt_url)

            if amount == Decimal("1.00"):
                await increment_requests(session, telegram_id, 1)
            elif amount == Decimal("190.00"):
                await increment_requests(session, telegram_id, 10)
            elif amount == Decimal("950.00"):
                await increment_requests(session, telegram_id, 50)

        # ✅ Фоновая отправка чека — не блокирует webhook
        if receipt_url:
            asyncio.create_task(send_receipt_async(telegram_id, receipt_url))

        return web.Response(status=200, text="OK")

    except Exception as e:
        print("Webhook error:", e)
        return web.Response(status=500, text="Internal error")