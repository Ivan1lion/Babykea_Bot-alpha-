"""
Инициализация VK-бота (Callback API).

VK шлёт POST-запросы на /vk/callback → aiohttp обрабатывает → вызывает хэндлеры.
В отличие от vkbottle Long Poll, здесь мы сами парсим события.

Необходимые переменные в .env:
  VK_GROUP_TOKEN        — токен сообщества (Настройки → Работа с API → Ключи доступа)
  VK_GROUP_ID           — ID группы (число)
  VK_SECRET             — секретный ключ (Callback API → Секретный ключ)
  VK_CONFIRMATION_CODE  — строка подтверждения сервера (Callback API)
"""

import os
import logging
from vkbottle.bot import Bot
from vkbottle import API

logger = logging.getLogger(__name__)

VK_GROUP_TOKEN = os.getenv("VK_GROUP_TOKEN", "")
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID", "0"))
VK_SECRET = os.getenv("VK_SECRET", "")
VK_CONFIRMATION_CODE = os.getenv("VK_CONFIRMATION_CODE", "")


def create_vk_bot() -> Bot:
    """Создаёт экземпляр VK-бота (используется для Long Poll, если понадобится)."""
    if not VK_GROUP_TOKEN:
        raise ValueError("VK_GROUP_TOKEN не задан в .env")
    bot = Bot(token=VK_GROUP_TOKEN)
    logger.info(f"VK Bot initialized for group {VK_GROUP_ID}")
    return bot


def create_vk_api() -> API:
    """Создаёт VK API клиент для отправки сообщений."""
    if not VK_GROUP_TOKEN:
        raise ValueError("VK_GROUP_TOKEN не задан в .env")
    return API(token=VK_GROUP_TOKEN)
