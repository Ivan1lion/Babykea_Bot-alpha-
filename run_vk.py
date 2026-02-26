"""
Точка входа: VK-бот (Callback API через aiohttp).

VK шлёт POST-запросы на /vk/callback.
Этот же сервер обслуживает webhook ЮKassa и лендинг оплаты.

Запуск:
  python run_vk.py

Docker Compose:
  command: python run_vk.py

Необходимые переменные .env:
  VK_GROUP_TOKEN, VK_GROUP_ID, VK_SECRET, VK_CONFIRMATION_CODE
"""

import asyncio
import os
import sys
import signal
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from aiohttp import web

from app.core.db.config import session_maker, engine
from app.core.redis_client import redis_client as redis
from app.platforms.vk.bot import create_vk_api, VK_GROUP_ID
from app.platforms.vk.callback import vk_callback_handler
from app.web.webhooks import yookassa_webhook_handler
from app.web.payment_landing import checkout_page, checkout_process, checkout_success

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

YOOKASSA_PATH = "/yookassa/webhook"
VK_CALLBACK_PATH = "/vk/callback"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8001  # Другой порт, чтобы не конфликтовать с TG-ботом


async def main():
    # === 1. Redis ===
    await redis.connect()

    # === 2. VK API ===
    vk_api = create_vk_api()
    logger.info(f"VK API initialized for group {VK_GROUP_ID}")

    # === 3. Aiohttp-сервер ===
    app = web.Application()

    # Передаём зависимости в app для доступа из хэндлеров
    app["vk_api"] = vk_api
    app["vk_bot"] = vk_api  # Для webhook уведомлений
    app["session_maker"] = session_maker

    # Маршруты
    async def health(request):
        return web.Response(text="ok")

    app.router.add_get("/health", health)
    app.router.add_post(VK_CALLBACK_PATH, vk_callback_handler)
    app.router.add_post(YOOKASSA_PATH, yookassa_webhook_handler)


    # === 4. Запуск ===
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=WEBAPP_HOST, port=WEBAPP_PORT)
    await site.start()
    logger.info(f"VK Bot server running on {WEBAPP_HOST}:{WEBAPP_PORT}")
    logger.info(f"Callback URL: /vk/callback")

    # === 5. Graceful shutdown ===
    stop_event = asyncio.Event()

    if os.name != "nt":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop_event.set)
        try:
            await stop_event.wait()
        finally:
            await _shutdown(runner)
    else:
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await _shutdown(runner)


async def _shutdown(runner):
    logger.info("🔄 VK Bot: shutting down...")
    await runner.cleanup()
    try:
        await engine.dispose()
    except Exception:
        pass
    try:
        await redis._client.aclose()
    except Exception:
        pass
    logger.info("✅ VK Bot: shutdown complete")


if __name__ == "__main__":
    try:
        if os.name == "nt":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
