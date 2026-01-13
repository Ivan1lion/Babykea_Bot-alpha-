import os
from aiogram.types import BotCommand
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, LinkPreviewOptions
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Router, Bot
from app.comands_menu.text_for_user import text_blog
from app.db.crud import stop_if_no_promo




menu_cmds_router = Router()


bot_menu = [
    BotCommand(command="what", description="⁉️ Как подобрать коляску"),
    BotCommand(command="where", description="💢 Как не сломать коляску"),
    BotCommand(command="when", description="✅ Как продлить жизнь коляске"),
    BotCommand(command="ai_consultant", description="🤖 AI консультант"),
    BotCommand(command="blog", description="️🧔‍♂️ Блог мастера"),
    BotCommand(command="help", description="🆘 Помощь"),
    BotCommand(command="config", description="⚙️ Мой профиль"),
    BotCommand(command="privacy", description="☑️ Политика конфиденциальности"),
    BotCommand(command="offer", description="📜 Оферта"),
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
async def policy_cmd(message: Message):
    await message.answer(f" 1. Карусель видеороликов о правилах правильной эксплуатации"
                         f"\n\n 2. Призыв перейти в раздел '💊 Как продлить жизнь коляске'")


@menu_cmds_router.message(Command("when"))
async def policy_cmd(message: Message):
    await message.answer(f" 1. Карусель видеороликов о ТО детской коляски"
                         f"\n\n 2. Запуск времени до планового ТО")


@menu_cmds_router.message(Command("ai_consultant"))
async def policy_cmd(message: Message, bot: Bot, session: AsyncSession):
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
async def policy_cmd(message: Message):
    await message.answer(text=text_blog, link_preview_options=LinkPreviewOptions(is_disabled=True))


@menu_cmds_router.message(Command("help"))
async def policy_cmd(message: Message):
    await message.answer(f" 1. Адрес магазина («Ваш магазин»)"
                         f"\n\n 2. Ответы на частые вопросы (Типовые и по модели коляски пользователя)")


@menu_cmds_router.message(Command("config"))
async def policy_cmd(message: Message):
    await message.answer(f" 1. Выбор статуса /quiz_restart"
                         f"\n\n 2. Указать ПДР или возраст ребенка (развития ребенка по месяцам (что и когда он "
                         f"должен делать), календарь прививок (показывает когда и какую нужно сделать плановую прививку)"
                         f"\n\n 3. Изменить время ТО")




@menu_cmds_router.message(Command("privacy"))
async def policy_cmd(message: Message):
    await message.answer(text_privacy)


@menu_cmds_router.message(Command("offer"))
async def offer_cmd(message: Message):
    await message.answer(text_offer)




