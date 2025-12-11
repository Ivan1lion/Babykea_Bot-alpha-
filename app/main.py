import asyncio
import os


from aiogram import Bot, Dispatcher, types, F
# from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
# from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
# from aiohttp import web


from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

# from app.db.config import create_db, drop_db, session_maker
# from app.db.crud import notify_pending_users, fetch_and_send_unsent_post
# from app.middlewares.db_session import DataBaseSession
from app.handlers.for_user import for_user_router
from app.comands_menu.bot_menu_cmds import bot_menu
# from app.openai_assistant.queue import OpenAIRequestQueue
# from app.payments.payment_routes import yookassa_webhook_handler





bot = Bot(token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(for_user_router)




async def on_startup(dispatcher: Dispatcher):
    print("GO bd")
    # await bot.set_webhook(
    #     url=WEBHOOK_URL,
    #     drop_pending_updates=True,
    #     allowed_updates=["message", "edited_message", "callback_query", "inline_query", "chosen_inline_result",
    #                      "callback_query", "shipping_query", "pre_checkout_query", "poll", "poll_answer",
    #                      "my_chat_member", "chat_member", "chat_join_request", "channel_post", "edited_channel_post"]
    # )
    await bot.set_my_description(description=f"🔥Этот бот поможет подобрать необходимую детскую коляску для Вас "
                                             f"\n\n- 000000000000000000 "
                                             f"\n- 000000000000000000 "
                                             f"\n- 000000000000000000 "
                                             f"\n\nДля запуска бота нажмите пожалуйста кнопку ниже👇")
    await bot.set_my_short_description(short_description=f"Сервис по подбору (поиску) детских колясок. Я разработал "
                                                         f"этого бота, чтобы помогать людям "
                                                         f"\n\nadmin: @RomanMo_admin")
    # await drop_db() # удаление Базы Данных
    # await create_db() # создание Базы Данных
    # global openai_queue
    # openai_queue = OpenAIRequestQueue()
    # await notify_pending_users(bot, session_maker)
    # async with session_maker() as session:
    #     await fetch_and_send_unsent_post(bot, session)


# async def on_shutdown(dispatcher: Dispatcher):
#     print("on_shutdown")
#     await bot.session.close()





async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    dp.startup.register(on_startup)
    # dp.shutdown.register(on_shutdown)
    # dp.update.middleware(DataBaseSession(session_pool=session_maker)) # Middleware сессии БД
    # await bot.set_my_commands(scope=types.BotCommandScopeAllPrivateChats) #команда для удаления кнопки меню
    await bot.set_my_commands(commands=bot_menu, scope=types.BotCommandScopeAllPrivateChats())
    await dp.start_polling(bot)








if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")