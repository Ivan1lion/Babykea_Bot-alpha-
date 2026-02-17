import asyncio
import os


from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.fsm.storage.memory import MemoryStorage # 👈 Добавили для Fallback если Redis лёг
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web


from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from app.db.config import session_maker
from app.middlewares.db_session import DataBaseSession
from app.middlewares.old_updates import DropOldUpdatesMiddleware
from app.handlers.for_user import for_user_router
from app.handlers.for_quiz import quiz_router
from app.comands_menu.standard_cmds import bot_menu
from app.comands_menu import menu_cmds_router
from app.payments.payment_routes import yookassa_webhook_handler
from app.redis_client import redis_client as redis



# Константы
WEBHOOK_PATH = "/webhook"           # для Telegram
YOOKASSA_PATH = "/yookassa/webhook" # для ЮKassa
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8000


# storage = RedisStorage(redis=redis, key_builder=DefaultKeyBuilder(with_bot_id=True))
bot = Bot(token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
# dp = Dispatcher(storage=storage)



# dp.include_router(menu_cmds_router)
# dp.include_router(quiz_router)
# dp.include_router(for_user_router)




async def on_startup(dispatcher: Dispatcher):
    print("Bot started ▶️")
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=False,
        allowed_updates=["message", "edited_message", "callback_query", "inline_query", "chosen_inline_result",
                         "callback_query", "shipping_query", "pre_checkout_query", "poll", "poll_answer",
                         "my_chat_member", "chat_member", "chat_join_request", "channel_post", "edited_channel_post"]
    )
    await bot.set_my_description(description=f"🔥Этот бот поможет подобрать необходимую детскую коляску для Вас "
                                             # f"\n\n- 000000000000000000 "
                                             # f"\n- 000000000000000000 "
                                             # f"\n- 000000000000000000 "
                                             f"\n\nДля запуска бота нажмите пожалуйста кнопку ниже👇")
    await bot.set_my_short_description(short_description=f"Сервис по подбору (поиску) детских колясок. Разработан "
                                                         f"для молодых родителей")




async def on_shutdown(dispatcher: Dispatcher):
    print("on_shutdown")
    await bot.session.close()
    await redis._client.close()





async def main():
    # === 1. ПОДКЛЮЧЕНИЕ К REDIS ===
    await redis.connect(bot=bot)
    # === 2. ВЫБОР ХРАНИЛИЩА (FSM) ===
    if redis._connected:
        # Если Redis жив — используем его.
        # ВАЖНО: передаем redis._client (оригинал), а не обертку!
        storage = RedisStorage(
            redis=redis._client,
            key_builder=DefaultKeyBuilder(with_bot_id=True)
        )
        print("✅ FSM: RedisStorage подключен")
    else:
        # Если Redis лежит — используем RAM, чтобы бот запустился
        storage = MemoryStorage()
        print("⚠️ FSM: Redis недоступен. Включен MemoryStorage (RAM)")

    # === 3. СОЗДАНИЕ ДИСПЕТЧЕРА ===
    # Создаем dp здесь, когда storage уже определен
    dp = Dispatcher(storage=storage)

    # Регистрируем роутеры
    dp.include_router(menu_cmds_router)
    dp.include_router(quiz_router)
    dp.include_router(for_user_router)

    # Регистрируем мидлвари
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.update.outer_middleware(DropOldUpdatesMiddleware(limit_seconds=60)) # Middleware для постинга
    dp.update.middleware(DataBaseSession(session_pool=session_maker)) # Middleware сессии БД

    # Установка команд
    await bot.set_my_commands(commands=bot_menu, scope=types.BotCommandScopeAllPrivateChats())

    # === 4. ЗАПУСК ВЕБ-СЕРВЕРА ===
    app = web.Application()
    app["bot"] = bot

    async def health(request):
        return web.Response(text="ok") # для проверки доступности контейнера и для Caddy
    app.router.add_get("/health", health)
    app.router.add_post(YOOKASSA_PATH, yookassa_webhook_handler)

    # Важно: передаем dp, который мы создали внутри main
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # 🚀 Запускаем aiohttp-сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=WEBAPP_HOST, port=WEBAPP_PORT)
    await site.start()
    print(f"Bot is running on {WEBAPP_HOST}:{WEBAPP_PORT}")
    print(f"Webhook URL: {WEBHOOK_URL}")
    # Держим процесс живым
    await asyncio.Event().wait()




if __name__ == "__main__":
    try:
        # На Windows иногда нужно явно задать политику цикла, если будут ошибки
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")