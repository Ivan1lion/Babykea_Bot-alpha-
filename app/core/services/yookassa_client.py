import base64
import os
import aiohttp


YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"


def _auth_header() -> str:
    raw = f"{os.getenv('YOOKASSA_SHOP_ID')}:{os.getenv('YOOKASSA_SECRET_KEY')}"
    return base64.b64encode(raw.encode()).decode()


async def fetch_payment(payment_id: str) -> dict:
    headers = {
        "Authorization": f"Basic {_auth_header()}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{YOOKASSA_API_URL}/{payment_id}",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
