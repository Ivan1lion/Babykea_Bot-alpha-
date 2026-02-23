import asyncio
import os
import signal
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from app.db.config import session_maker, engine
from app.middlewares.db_session import DataBaseSession
from app.middlewares.old_updates import DropOldUpdatesMiddleware
from app.handlers.for_user import for_user_router
from app.handlers.for_quiz import quiz_router
from app.comands_menu.standard_cmds import bot_menu
from app.comands_menu import menu_cmds_router
from app.payments.payment_routes import yookassa_webhook_handler
from app.redis_client import redis_client as redis
from app.services.service_worker import run_service_notifications
from app.services.search_service import chroma_client

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, #При деплое поставить level=logging.WARNING что бы не засорять терминал лишними логами
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

# Константы
WEBHOOK_PATH = "/webhook"
YOOKASSA_PATH = "/yookassa/webhook"
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8000


bot = Bot(token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def on_startup(dispatcher: Dispatcher):
    logger.info("Bot started ▶️")
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=False,
        allowed_updates=["message", "edited_message", "callback_query", "inline_query", "chosen_inline_result",
                         "callback_query", "shipping_query", "pre_checkout_query", "poll", "poll_answer",
                         "my_chat_member", "chat_member", "chat_join_request", "channel_post", "edited_channel_post"]
    )
    await bot.set_my_description(description=f"👋 Меня зовут Иван, я мастер по ремонту детских колясок"
                                             f"\n\n🔍 Ещё выбираете? Найдем надежную модель под ваши условия "
                                             f"(AI-подбор + мои видеорекомендации)"
                                             f"\n\n🛠 Уже купили? Покажу, что нужно сделать сразу после покупки, а "
                                             f"чего с коляской делать КАТЕГОРИЧЕСКИ нельзя (80% поломок происходит "
                                             f"по вине владельцев колясок!)"
                                             f"\n\nНажмите кнопку ниже, чтобы начать 👇")
    await bot.set_my_short_description(short_description=f"Подбор (поиск) и тонкости эксплуатации детских колясок")


async def graceful_shutdown(worker_task: asyncio.Task, runner: web.AppRunner):
    """
    Единая точка завершения — вызывается и при SIGTERM (Linux/Docker),
    и при Ctrl+C (Windows/Linux локально).
    """
    logger.info("🔄 Начинаем graceful shutdown...")

    # 1. Останавливаем воркер
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    # 2. Закрываем aiohttp (внутри вызывает on_shutdown через dp)
    await runner.cleanup()

    logger.info("✅ Graceful shutdown завершён")


async def on_shutdown(dispatcher: Dispatcher):
    logger.info("⏹️ Завершение работы бота...")

    # 1. Закрываем ChromaDB — сбрасывает буферы на диск, защищает chroma.sqlite3 от порчи
    try:
        chroma_client._system.stop()
        logger.info("✅ ChromaDB остановлен корректно")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при остановке ChromaDB: {e}")

    # 2. Закрываем пул соединений PostgreSQL
    # Без этого при рестартах в БД накапливаются "мёртвые" соединения
    try:
        await engine.dispose()
        logger.info("✅ PostgreSQL: пул соединений закрыт")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при закрытии PostgreSQL: {e}")

    # 3. Закрываем сессию бота
    await bot.session.close()

    # 4. Закрываем Redis
    try:
        await redis._client.close()
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при закрытии Redis: {e}")

    logger.info("✅ on_shutdown завершён")


async def main():
    # === 1. ПОДКЛЮЧЕНИЕ К REDIS ===
    await redis.connect(bot=bot)

    # === 2. ВЫБОР ХРАНИЛИЩА (FSM) ===
    if redis._connected:
        storage = RedisStorage(
            redis=redis._client,
            key_builder=DefaultKeyBuilder(with_bot_id=True)
        )
        logger.info("✅ FSM: RedisStorage подключен")
    else:
        storage = MemoryStorage()
        logger.warning("⚠️ FSM: Redis недоступен. Включен MemoryStorage (RAM)")

    # === 3. СОЗДАНИЕ ДИСПЕТЧЕРА ===
    dp = Dispatcher(storage=storage)

    dp.include_router(menu_cmds_router)
    dp.include_router(quiz_router)
    dp.include_router(for_user_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.update.outer_middleware(DropOldUpdatesMiddleware(limit_seconds=60))
    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    await bot.set_my_commands(commands=bot_menu, scope=types.BotCommandScopeAllPrivateChats())

    # === 4. ЗАПУСК ВЕБ-СЕРВЕРА ===
    app = web.Application()
    app["bot"] = bot

    async def health(request):
        return web.Response(text="ok")  # для Caddy и healthcheck

    app.router.add_get("/health", health)
    app.router.add_post(YOOKASSA_PATH, yookassa_webhook_handler)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=WEBAPP_HOST, port=WEBAPP_PORT)
    await site.start()
    logger.info(f"Bot is running on {WEBAPP_HOST}:{WEBAPP_PORT}")
    logger.info(f"Webhook URL: {WEBHOOK_URL}")

    # === 6. ЗАПУСКАЕМ ВОРКЕР ТЕХ. ОБСЛУЖИВАНИЯ ===
    worker_task = asyncio.create_task(run_service_notifications(bot, session_maker))

    # ================================================================
    # === 5. ОБРАБОТКА СИГНАЛОВ ОСТАНОВКИ ===
    # ================================================================

    IS_LINUX = os.name != "nt"  # True на сервере, False на Windows

    stop_event = asyncio.Event()

    if IS_LINUX:
        # 🐧 LINUX / DOCKER (продакшен):
        # loop.add_signal_handler — единственный правильный способ перехватить
        # SIGTERM (docker stop) в asyncio на Linux.
        # На Windows этот метод не реализован (NotImplementedError).
        def _handle_signal():
            logger.info("🛑 Получен сигнал остановки (SIGTERM/SIGINT)")
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _handle_signal)  # 🐧 только Linux

        # Держим процесс живым до сигнала.
        # try/finally гарантирует запуск graceful_shutdown даже если
        # что-то неожиданно прервёт ожидание.
        try:
            await stop_event.wait()
        finally:
            await graceful_shutdown(worker_task, runner)

    else:
        # 🪟 WINDOWS / ЛОКАЛЬНОЕ ТЕСТИРОВАНИЕ:
        # add_signal_handler не работает на Windows — используем простое
        # бесконечное ожидание. Остановка — Ctrl+C в консоли.
        # KeyboardInterrupt перехватывается в блоке except ниже
        # и запускает graceful_shutdown.
        try:
            await asyncio.Event().wait()  # 🪟 только Windows (локальный тест)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await graceful_shutdown(worker_task, runner)


if __name__ == "__main__":
    try:
        if os.name == 'nt':
            # 🪟 Windows: обязательная политика для корректной работы asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        # Ctrl+C при старте (до запуска event loop) — тихий выход
        print("Exit")
        pass  # Убрать print("Exit"), так как logger всё выведет