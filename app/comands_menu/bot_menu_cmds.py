import os
from aiogram.types import BotCommand
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Router, Bot
from app.comands_menu.text_for_user import text_privacy, text_offer, text_hello, text_info, text_hello2




menu_cmds_router = Router()


bot_menu = [
    BotCommand(command="start", description="🔄 Перезапуск"),
    BotCommand(command="info", description="🤖 Как пользоваться ботом"),
    BotCommand(command="balance", description="⭐️ Баланс (кол-во запросов)"),
    BotCommand(command="hello", description="👋 ПРИВЕТ"),
    BotCommand(command="privacy", description="☑️ Политика конфиденциальности"),
    BotCommand(command="offer", description="📜 Оферта"),
]


# команды для кнопки МЕНЮ
@menu_cmds_router.message(Command("info"))
async def policy_cmd(message: Message):
    await message.answer(text_info)


@menu_cmds_router.message(Command("balance"))
async def policy_cmd(message: Message, bot: Bot, session: AsyncSession):
    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = result.scalar_one_or_none()
    if user.requests_left == 0:
        await message.answer(f"🚫 У вас закончились запросы"
                             f"\n\nПожалуйста, пополните баланс", reply_markup=kb.pay)
        return
    text_balance = (f"Количество запросов\n"
                    f"на вашем балансе: [ {user.requests_left} ]"
                    f"\n\nПополнить баланс можно через кнопки ниже")
    await message.answer(text_balance, reply_markup=kb.pay)


@menu_cmds_router.message(Command("hello"))
async def offer_cmd(message: Message):
    # Получаем абсолютный путь к медиа-файлу
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    GIF_PATH = os.path.join(BASE_DIR, "..", "mediafile_for_bot", "My_photo.png")
    gif_file = FSInputFile(GIF_PATH)
    # Отправляем медиа
    wait_msg = await message.answer_photo(photo=gif_file, caption=text_hello)
    await message.answer(text_hello2)


@menu_cmds_router.message(Command("privacy"))
async def policy_cmd(message: Message):
    await message.answer(text_privacy)


@menu_cmds_router.message(Command("offer"))
async def offer_cmd(message: Message):
    await message.answer(text_offer)




