import os
import asyncio
from aiogram.types import BotCommand
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, LinkPreviewOptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Router, Bot
from aiogram.exceptions import TelegramBadRequest
from app.comands_menu.text_for_user import text_offer
from app.db.models import User, Magazine
from app.db.crud import stop_if_no_promo
from app.handlers.keyboards import magazine_map_kb, get_ai_mode_kb
import app.handlers.keyboards as kb





menu_cmds_router = Router()


bot_menu = [
    BotCommand(command="what", description="⁉️ Как подобрать коляску"),
    BotCommand(command="where", description="💢 Как не сломать коляску"),
    BotCommand(command="when", description="✅ Как продлить жизнь коляске"),
    BotCommand(command="ai_consultant", description="🤖 AI-консультант"),
    BotCommand(command="blog", description="️🧔‍♂️ Блог мастера"),
    BotCommand(command="help", description="🆘 Помощь"),
    BotCommand(command="config", description="👤 Мой профиль"),
    BotCommand(command="contacts", description="📍 Магазин колясок"),
    BotCommand(command="offer", description="📜 Пользовательское соглашение"),
]


# команды для кнопки МЕНЮ
@menu_cmds_router.message(Command("what"))
async def policy_cmd(message: Message, session: AsyncSession):

    if await stop_if_no_promo(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о нюансах подбора детской коляски"
                         f"\n\n 2. Квиз по подбору типа коляски"
                         f"\n\n 3. Тригер про AI с призывам сделать запрос")




@menu_cmds_router.message(Command("where"))
async def policy_cmd(message: Message, session: AsyncSession):

    if await stop_if_no_promo(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о правилах правильной эксплуатации"
                         f"\n\n 2. Призыв перейти в раздел '💊 Как продлить жизнь коляске'")




@menu_cmds_router.message(Command("when"))
async def policy_cmd(message: Message, session: AsyncSession):

    if await stop_if_no_promo(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о ТО детской коляски"
                         f"\n\n 2. Запуск времени до планового ТО")




@menu_cmds_router.message(Command("ai_consultant"))
async def cmd_ai_consultant(message: Message, bot:Bot, session: AsyncSession):
    if await stop_if_no_promo(message=message, session=session):
        return

    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = result.scalar_one_or_none()
    # 3. ЛОГИКА ПРОВЕРКИ
    # Условие: is_first_request = False И show_intro_message = True
    if user.show_intro_message:
        # Меняем флаг на False, чтобы это сообщение больше не показывалось
        user.show_intro_message = False
        await session.commit()  # Сохраняем изменение в БД

        # Отправляем "Красивое" сообщение (copy_message)
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=-1003498991864,  # ID группы
                message_id=4,  # ID сообщения из группы
            )
            await asyncio.sleep(1)
            await message.answer(
                text="AI-консультант готов к работе!\n\n"
                     "Он умеет подбирать коляски, а также отвечать на любые вопросы по эксплуатации\n\n"
                     "👇 Выберите режим работы:"
                     "\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
                     "\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализ и "
                     "сравнения уже известных Вам моделей колясок",
                reply_markup=get_ai_mode_kb()
            )
        except TelegramBadRequest:
            # Получаем абсолютный путь к медиа-файлу
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            GIF_PATH = os.path.join(BASE_DIR, "..", "mediafile_for_bot", "video.mp4")
            gif_file = FSInputFile(GIF_PATH)
            # Отправляем медиа
            wait_msg = await message.answer_video(
                video=gif_file,
                caption="AI-консультант готов к работе!\n\n"
                        "Он умеет подбирать коляски, а также отвечать на любые вопросы по эксплуатации\n\n"
                        "👇 Выберите режим работы:"
                        "\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
                        "\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализ и "
                        "сравнения уже известных Вам моделей колясок",
                supports_streaming=True,
                reply_markup=get_ai_mode_kb()
            )

    else:
        # ИНАЧЕ -> Отправляем обычное сообщение
        await message.answer(
            text=f"👋 Чтобы я мог помочь, выберите, пожалуйста, режим работы:"
            f"\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
            f"\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализ и сравнения уже известных "
            f"Вам моделей колясок"
            f"\n\n<blockquote>Количество запросов\n"
            f"на вашем балансе: [ {user.requests_left} ]</blockquote>",
            reply_markup=kb.get_ai_mode_with_balance_kb()
        )







@menu_cmds_router.message(Command("blog"))
async def policy_cmd(message: Message, bot: Bot, session: AsyncSession):

    if await stop_if_no_promo(message=message, session=session):
        return

    await bot.forward_message(
        chat_id=message.chat.id,
        from_chat_id=-1003540154410,  # ID группы
        message_id=7  # ID сообщения из группы
    )




@menu_cmds_router.message(Command("help"))
async def policy_cmd(message: Message, session: AsyncSession):

    if await stop_if_no_promo(message=message, session=session):
        return

    await message.answer(f" 1. Адрес магазина («Ваш магазин»)"
                         f"\n\n 2. Ответы на частые вопросы (Типовые и по модели коляски пользователя)")




@menu_cmds_router.message(Command("config"))
async def policy_cmd(message: Message, session: AsyncSession):

    if await stop_if_no_promo(message=message, session=session):
        return

    await message.answer(f"1. /quiz_restart - пройти квиз-опрос заново"
                         f"<blockquote>На основании ваших ответов AI-консультант подбирает и сравнивает коляски, "
                         f"соответствующие запросу</blockquote>"
                         f"\n\n/email - указать email для получения чеков"
                         f"<blockquote>При необходимости вы можете указать свой email для получения чеков  об оплате "
                         f"на свою почту</blockquote>"
                         f"\n\n2. Изменить время ТО"
                         f"\n\n3. Сохраненная информация")




@menu_cmds_router.message(Command("contacts"))
async def policy_cmd(message: Message, session: AsyncSession):

    if await stop_if_no_promo(message=message, session=session):
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

    # 🔹 Спец-логика для Babykea
    if magazine.name == "Babykea":
        await message.answer_photo(
            photo="https://i.postimg.cc/zBSgzjss/i.jpg",
            caption=(
                "🏆 <b>Магазины с высокой репутацией</b>\n\n"
                "• Первая коляска\n"
                "• Boan Baby\n"
                "• Lapsi"
            ),
        )
        return

    # 🔹 Обычные магазины
    text_parts = [
        f"<blockquote>{magazine.name}</blockquote>\n",
        f"📍 Город: {magazine.city}",
        f"🏠 Адрес: {magazine.address}",
        f"🌐 Сайт: <a href='{magazine.url_website}'>{magazine.name_website}</a>",
    ]

    if magazine.username_magazine:
        text_parts.append(f"💬 Telegram: {magazine.username_magazine}")

    text = "\n".join(text_parts)

    if magazine.photo:
        await message.answer_photo(
            photo=magazine.photo,
            caption=text,
            reply_markup=magazine_map_kb(magazine.map_url),
        )
    else:
        await message.answer(
            text,
            reply_markup=magazine_map_kb(magazine.map_url),
        )




@menu_cmds_router.message(Command("offer"))
async def offer_cmd(message: Message):
    await message.answer(text=text_offer, link_preview_options=LinkPreviewOptions(is_disabled=True))




