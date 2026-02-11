from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import closed_menu


info_router = Router()

@info_router.message(Command("what"))
async def what_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о нюансах подбора детской коляски"
                         f"\n\n 2. Квиз по подбору типа коляски"
                         f"\n\n 3. Тригер про AI с призывам сделать запрос")




@info_router.message(Command("where"))
async def where_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о правилах правильной эксплуатации"
                         f"\n\n 2. Призыв перейти в раздел '💊 Как продлить жизнь коляске'")




@info_router.message(Command("when"))
async def when_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о ТО детской коляски"
                         f"\n\n 2. Запуск времени до планового ТО")