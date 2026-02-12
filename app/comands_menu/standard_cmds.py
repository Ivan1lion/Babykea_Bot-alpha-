from aiogram import Router, Bot
from aiogram.types import Message, BotCommand, LinkPreviewOptions
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import closed_menu


standard_router = Router()


bot_menu = [
    BotCommand(command="what", description="⁉️ Как подобрать коляску"),
    BotCommand(command="where", description="💢 Как не сломать коляску"),
    BotCommand(command="when", description="✅ Как продлить жизнь коляске"),
    BotCommand(command="ai_consultant", description="🤖 AI-консультант"),
    BotCommand(command="blog", description="️🧔‍♂️ Блог мастера"),
    BotCommand(command="help", description="🆘 Помощь"),
    BotCommand(command="config", description="👤 Мой профиль"),
    BotCommand(command="contacts", description="📍 Магазин колясок"),
    BotCommand(command="offer", description="📃 Пользовательское соглашение"),
]




@standard_router.message(Command("blog"))
async def blog_cmd(message: Message, bot: Bot, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await bot.forward_message(
        chat_id=message.chat.id,
        from_chat_id=-1003540154410,  # ID группы
        message_id=7  # ID сообщения из группы
    )





@standard_router.message(Command("offer"))
async def offer_cmd(message: Message):
    text_offer = (f"1. <a href='https://telegra.ph/Oferta-dlya-chat-bota-Babykea-Bot-Babykea-07-14'>Публичная оферта, "
                  f"Пользовательское соглашение, условия эксплуатации и обслуживания</a>\n\n"
                  f"2. <a href='https://telegra.ph/Politika-konfidencialnosti-07-26-9'>Политика Конфиденциальности</a>")
    await message.answer(text=text_offer, link_preview_options=LinkPreviewOptions(is_disabled=True))