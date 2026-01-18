import asyncio
import os


from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web


from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from app.db.config import create_db, drop_db, session_maker
from app.middlewares.db_session import DataBaseSession
from app.handlers.for_user import for_user_router
from app.handlers.for_quiz import quiz_router
from app.comands_menu.bot_menu_cmds import bot_menu, menu_cmds_router
from app.posting.queue import start_sender
from app.payments.payment_routes import yookassa_webhook_handler





storage = MemoryStorage()
bot = Bot(token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

dp.include_router(menu_cmds_router)
dp.include_router(quiz_router)
dp.include_router(for_user_router)




# Константы
WEBHOOK_PATH = "/webhook"           # для Telegram
YOOKASSA_PATH = "/yookassa/webhook" # для ЮKassa
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8000




async def on_startup(dispatcher: Dispatcher):
    print("Bot started ▶️")
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True,
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
    asyncio.create_task(start_sender(bot)) # 🔹 запуск очереди рассылки (ВАЖНО)



async def on_shutdown(dispatcher: Dispatcher):
    print("on_shutdown")
    await bot.session.close()





async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.update.middleware(DataBaseSession(session_pool=session_maker)) # Middleware сессии БД
    await bot.set_my_commands(commands=bot_menu, scope=types.BotCommandScopeAllPrivateChats())
    # await dp.start_polling(bot)

    # 🌐 Создаём веб-приложение
    app = web.Application()

    async def health(request):
        return web.Response(text="ok")  # для проверки доступности контейнера и для Caddy

    app.router.add_get("/health", health)

    app.router.add_post(YOOKASSA_PATH, yookassa_webhook_handler)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    app.on_shutdown.append(on_shutdown)

    # 🚀 Запускаем aiohttp-сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=WEBAPP_HOST, port=WEBAPP_PORT)
    await site.start()

    print(f"Bot is running on {WEBAPP_HOST}:{WEBAPP_PORT}")
    print(f"Webhook URL: {WEBHOOK_URL}")

    # 🕒 Бесконечное ожидание (держим процесс живым)
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")