from aiohttp import web
import json
import os
from app.payments.yookassa_client import verify_yookassa_signature
from app.db.config import session_maker
from app.db.crud import increment_requests


async def yookassa_webhook_handler(request: web.Request):
    try:
        body = await request.read()
        signature = request.headers.get("Content-HMAC-SHA256")

        data = json.loads(body)
        if data.get("event") != "payment.succeeded":
            return web.Response(status=200, text="Ignored")

        payment_data = data["object"]
        amount = float(payment_data["amount"]["value"])
        telegram_id = int(payment_data["metadata"]["telegram_id"])

        async with session_maker() as session:
            if amount == 30:
                await increment_requests(session, telegram_id, count=1)
            elif amount == 550:
                await increment_requests(session, telegram_id, count=20)
            elif amount == 2500:
                await increment_requests(session, telegram_id, count=100)

        return web.Response(status=200, text="OK")
    except Exception as e:
        return web.Response(status=500, text=f"Error: {e}")

