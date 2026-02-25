"""
Единое платёжное ядро.
Не знает ни про Telegram, ни про VK — только про ЮKassa и БД.
"""

import os
import base64
import logging
from uuid import uuid4
from decimal import Decimal
from dataclasses import dataclass

import aiohttp
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import User, Payment, PaymentSession
from app.core.services.pay_config import PAYMENTS

logger = logging.getLogger(__name__)

YOOKASSA_API = "https://api.yookassa.ru/v3/payments"


def _auth_header() -> str:
    raw = f"{os.getenv('YOOKASSA_SHOP_ID')}:{os.getenv('YOOKASSA_SECRET_KEY')}"
    return base64.b64encode(raw.encode()).decode()


@dataclass
class PaymentResult:
    """Результат создания платежа."""
    success: bool
    confirmation_url: str | None = None
    payment_id: str | None = None
    error: str | None = None


async def create_yookassa_payment(
    session: AsyncSession,
    telegram_id: int | None = None,
    vk_id: int | None = None,
    payment_type: str = "",
    platform: str = "telegram",
    return_url: str = "",
) -> PaymentResult:
    """
    Создаёт платёж в ЮKassa и сохраняет pending-запись в БД.

    Вызывается из:
      - Telegram-хэндлера (напрямую или через лендинг)
      - VK-хэндлера
      - Web-лендинга

    Returns:
        PaymentResult с confirmation_url для редиректа юзера.
    """
    cfg = PAYMENTS.get(payment_type)
    if not cfg:
        return PaymentResult(success=False, error="Неизвестный тариф")

    amount = cfg["amount"]

    # Определяем user_id для поиска email
    user_filter = (
        User.telegram_id == telegram_id if telegram_id
        else User.vk_id == vk_id
    )

    result = await session.execute(select(User).where(user_filter))
    user = result.scalar_one_or_none()
    if not user:
        return PaymentResult(success=False, error="Пользователь не найден")

    receipt_email = user.email if user.email else "prokolyasky@yandex.ru"

    # Payload для ЮKassa
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
            "telegram_id": str(telegram_id or ""),
            "vk_id": str(vk_id or ""),
            "payment_type": payment_type,
            "platform": platform,
        },
        "receipt": {
            "customer": {
                "email": receipt_email,
            },
            "tax_system_code": 2,
            "items": [
                {
                    "description": "Доступ к функционалу бота",
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

    headers = {
        "Authorization": f"Basic {_auth_header()}",
        "Content-Type": "application/json",
        "Idempotence-Key": str(uuid4()),
    }

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                YOOKASSA_API,
                json=payment_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                payment_response = await resp.json()

        if "confirmation" not in payment_response:
            error_text = payment_response.get("description", "Нет confirmation")
            logger.error(f"ЮKassa error: {error_text}")
            return PaymentResult(success=False, error=f"Ошибка ЮKassa: {error_text}")

        payment_id = payment_response["id"]
        confirmation_url = payment_response["confirmation"]["confirmation_url"]

        # Сохраняем pending-платёж в БД
        payment = Payment(
            payment_id=payment_id,
            telegram_id=telegram_id or 0,
            amount=Decimal(str(amount)),
            status="pending",
            platform=platform,
        )
        session.add(payment)
        await session.commit()

        return PaymentResult(
            success=True,
            confirmation_url=confirmation_url,
            payment_id=payment_id,
        )

    except Exception as e:
        logger.exception(f"Ошибка создания платежа: {e}")
        return PaymentResult(success=False, error="Ошибка при создании платежа")


async def create_payment_session(
    session: AsyncSession,
    telegram_id: int | None = None,
    vk_id: int | None = None,
    payment_type: str = "",
    platform: str = "telegram",
) -> PaymentSession | None:
    """
    Создаёт PaymentSession для лендинга.

    Юзер получает ссылку /checkout/{token}, а на лендинге
    уже вызывается create_yookassa_payment().
    """
    cfg = PAYMENTS.get(payment_type)
    if not cfg:
        return None

    ps = PaymentSession(
        telegram_id=telegram_id,
        vk_id=vk_id,
        platform=platform,
        payment_type=payment_type,
        amount=Decimal(str(cfg["amount"])),
    )
    session.add(ps)
    await session.commit()
    await session.refresh(ps)
    return ps