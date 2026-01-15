import os
from aiogram.types import BotCommand
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, LinkPreviewOptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Router, Bot
from app.comands_menu.text_for_user import text_offer
from app.db.models import User, Magazine
from app.db.crud import stop_if_no_promo
from app.handlers.keyboards import magazine_map_kb





menu_cmds_router = Router()


bot_menu = [
    BotCommand(command="what", description="⁉️ Как подобрать коляску"),
    BotCommand(command="where", description="💢 Как не сломать коляску"),
    BotCommand(command="when", description="✅ Как продлить жизнь коляске"),
    BotCommand(command="ai_consultant", description="🤖 AI консультант"),
    BotCommand(command="blog", description="️🧔‍♂️ Блог мастера"),
    BotCommand(command="help", description="🆘 Помощь"),
    BotCommand(command="config", description="👤 Мой профиль"),
    BotCommand(command="contacts", description="📍 Магазин колясок"),
    BotCommand(command="offer", description="📜 Пользовательское соглашение"),
]


# команды для кнопки МЕНЮ
@menu_cmds_router.message(Command("what"))
async def policy_cmd(message: Message, session: AsyncSession):
    should_stop = await stop_if_no_promo(
        message=message,
        session=session,
    )
    if should_stop:
        return

    await message.answer(f" 1. Карусель видеороликов о нюансах подбора детской коляски"
                         f"\n\n 2. Квиз по подбору типа коляски"
                         f"\n\n 3. Тригер про AI с призывам сделать запрос")


@menu_cmds_router.message(Command("where"))
async def policy_cmd(message: Message, session: AsyncSession):
    should_stop = await stop_if_no_promo(
        message=message,
        session=session,
    )
    if should_stop:
        return

    await message.answer(f" 1. Карусель видеороликов о правилах правильной эксплуатации"
                         f"\n\n 2. Призыв перейти в раздел '💊 Как продлить жизнь коляске'")


@menu_cmds_router.message(Command("when"))
async def policy_cmd(message: Message, session: AsyncSession):
    should_stop = await stop_if_no_promo(
        message=message,
        session=session,
    )
    if should_stop:
        return

    await message.answer(f" 1. Карусель видеороликов о ТО детской коляски"
                         f"\n\n 2. Запуск времени до планового ТО")


@menu_cmds_router.message(Command("ai_consultant"))
async def policy_cmd(message: Message, bot: Bot, session: AsyncSession):
    should_stop = await stop_if_no_promo(
        message=message,
        session=session,
    )
    if should_stop:
        return

    await message.answer(f" 1. Видео или статья о том как пользоваться консультантом"
                         f"\n\n 2. Баланс (кол-во запросов)")
    # result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    # user = result.scalar_one_or_none()
    # if user.requests_left == 0:
    #     await message.answer(f"🚫 У вас закончились запросы"
    #                          f"\n\nПожалуйста, пополните баланс", reply_markup=kb.pay)
    #     return
    # text_balance = (f"Количество запросов\n"
    #                 f"на вашем балансе: [ {user.requests_left} ]"
    #                 f"\n\nПополнить баланс можно через кнопки ниже")
    # await message.answer(text_balance, reply_markup=kb.pay)


@menu_cmds_router.message(Command("blog"))
async def policy_cmd(message: Message, bot: Bot, session: AsyncSession):
    should_stop = await stop_if_no_promo(
        message=message,
        session=session,
    )
    if should_stop:
        return

    await bot.forward_message(
        chat_id=message.chat.id,
        from_chat_id=-1003540154410,  # ID группы
        message_id=7  # ID сообщения из группы
    )


@menu_cmds_router.message(Command("help"))
async def policy_cmd(message: Message, session: AsyncSession):
    should_stop = await stop_if_no_promo(
        message=message,
        session=session,
    )
    if should_stop:
        return

    await message.answer(f" 1. Адрес магазина («Ваш магазин»)"
                         f"\n\n 2. Ответы на частые вопросы (Типовые и по модели коляски пользователя)")


@menu_cmds_router.message(Command("config"))
async def policy_cmd(message: Message, session: AsyncSession):
    should_stop = await stop_if_no_promo(
        message=message,
        session=session,
    )
    if should_stop:
        return

    await message.answer(f"1. Выбор статуса /quiz_restart"
                         f"\n\n2. Указать ПДР или возраст ребенка (развития ребенка по месяцам (что и когда он "
                         f"должен делать), календарь прививок (показывает когда и какую нужно сделать плановую прививку)"
                         f"\n\n3. Изменить время ТО"
                         f"\n\n4. Созраненная информация")




@menu_cmds_router.message(Command("contacts"))
async def policy_cmd(message: Message, session: AsyncSession):
    should_stop = await stop_if_no_promo(
        message=message,
        session=session,
    )
    if should_stop:
        return

    result = await session.execute(
        select(Magazine)
        .join(User, User.magazine_id == Magazine.id)
        .where(User.telegram_id == message.from_user.id)
    )
    magazine = result.scalar_one_or_none()

    if not magazine:
        await message.answer("Магазин не найден")
        return

    text_parts = [
        f"<blockquote>{magazine.name}</blockquote>\n\n"
        f"📍 Город: {magazine.city}\n"
        f"🏠 Адрес: {magazine.address}\n"
        f"🌐 Сайт: <a href='{magazine.url_website}'>{magazine.name_website}</a>\n",
    ]
    if magazine.username_magazine:
        text_parts.append(f"💬 Telegram: {magazine.username_magazine}")

    await message.answer(
        "\n".join(text_parts),
        reply_markup=magazine_map_kb(magazine.map_url),
    )


@menu_cmds_router.message(Command("offer"))
async def offer_cmd(message: Message):
    await message.answer(text=text_offer, link_preview_options=LinkPreviewOptions(is_disabled=True))




