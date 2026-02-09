import os
import re
import asyncio
from aiogram import Router, Bot, F
from aiogram.types import BotCommand
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, FSInputFile, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, Magazine
from app.db.crud import closed_menu
from app.comands_menu.states import MenuStates
from app.comands_menu.crud_for_menu import update_user_email
from app.handlers.keyboards import magazine_map_kb
import app.handlers.keyboards as kb
from app.redis_client import redis_client
from app.services.user_service import get_user_cached, update_user_requests, update_user_flags



# Простая регулярка для email
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

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
    BotCommand(command="offer", description="📃 Пользовательское соглашение"),
]


# команды для кнопки МЕНЮ
@menu_cmds_router.message(Command("what"))
async def what_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о нюансах подбора детской коляски"
                         f"\n\n 2. Квиз по подбору типа коляски"
                         f"\n\n 3. Тригер про AI с призывам сделать запрос")




@menu_cmds_router.message(Command("where"))
async def where_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о правилах правильной эксплуатации"
                         f"\n\n 2. Призыв перейти в раздел '💊 Как продлить жизнь коляске'")




@menu_cmds_router.message(Command("when"))
async def when_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о ТО детской коляски"
                         f"\n\n 2. Запуск времени до планового ТО")




@menu_cmds_router.message(Command("ai_consultant"))
async def cmd_ai_consultant(message: Message, bot:Bot, session: AsyncSession):
    if await closed_menu(message=message, session=session):
        return

    # 🚀 Получаем данные мгновенно из Redis
    user = await get_user_cached(session, message.from_user.id)
    # ЛОГИКА ПРОВЕРКИ
    # Условие: is_first_request = False И show_intro_message = True
    if user.show_intro_message:
        # Меняем флаг на False, чтобы это сообщение больше не показывалось
        # 🚀 Обновляем флаг через Redis (БД обновляется, кэш сбрасывается)
        await update_user_flags(session, user.telegram_id, show_intro_message=False)

        # 1. Пытаемся отправить мгновенно через Redis (PRO способ)
        # Мы ищем file_id, который сохранили под именем "ai_intro"
        video_note_id = await redis_client.get("media:ai_intro")

        if video_note_id:
            try:
                await message.answer_video_note(
                    video_note=video_note_id
                )
                await asyncio.sleep(1)
                await message.answer(
                    text="AI-консультант готов к работе!\n\n"
                         "Он умеет подбирать коляски, а также отвечать на любые вопросы по эксплуатации\n\n"
                         "👇 Выберите режим работы:"
                         "\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
                         "\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализа и "
                         "сравнения уже известных Вам моделей колясок",
                    reply_markup=kb.get_ai_mode_kb()
                )
                print(f"🔔 ПОПЫТКА 1 для AI: Redis)")
                return  # Успех, выходим
            except Exception as e:
                logger.error(f"Ошибка отправки video_note из Redis: {e}")

        # 2. Если Рэдис сдох. Отправляем "Красивое" сообщение из канала (copy_message)
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=-1003498991864,  # ID группы
                message_id=28,  # ID сообщения из группы
            )
            await asyncio.sleep(1)
            await message.answer(
                text="AI-консультант готов к работе!\n\n"
                     "Он умеет подбирать коляски, а также отвечать на любые вопросы по эксплуатации\n\n"
                     "👇 Выберите режим работы:"
                     "\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
                     "\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализа и "
                     "сравнения уже известных Вам моделей колясок",
                reply_markup=kb.get_ai_mode_kb()
            )
            print(f"🔔 ПОПЫТКА 2 для AI: Redis)")
        except TelegramBadRequest:
            # Получаем абсолютный путь к медиа-файлу
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            GIF_PATH = os.path.join(BASE_DIR, "..", "mediafile_for_bot", "video.mp4")
            gif_file = FSInputFile(GIF_PATH)
            # Отправляем медиа
            await message.answer_video(
                video=gif_file,
                supports_streaming=True
            )
            await asyncio.sleep(1)
            await message.answer(
                text="AI-консультант готов к работе!\n\n"
                        "Он умеет подбирать коляски, а также отвечать на любые вопросы по эксплуатации\n\n"
                        "👇 Выберите режим работы:"
                        "\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
                        "\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализа и "
                        "сравнения уже известных Вам моделей колясок",
                reply_markup=kb.get_ai_mode_kb()
            )

    else:
        # Делаем "точечный" запрос в БД только за балансом
        # Это гарантирует 100% точность, игнорируя старый кэш
        result = await session.execute(
            select(User.requests_left).where(User.telegram_id == message.from_user.id)
        )
        # Если база вернет None (маловероятно), подстрахуемся 0
        real_balance = result.scalar_one_or_none() or 0
        await message.answer(
            text=f"👋 Чтобы я мог помочь, выберите, пожалуйста, режим работы:"
            f"\n\n<b>[Подобрать коляску]</b> - только для поиска (подбора) подходящей для Вас коляски"
            f"\n\n<b>[Другой запрос]</b> - для консультаций, решений вопросов по эксплуатации,анализа и сравнения уже известных "
            f"Вам моделей колясок"
            f"\n\n<blockquote>Количество запросов\n"
            f"на вашем балансе: [ {real_balance} ]</blockquote>",
            reply_markup=kb.get_ai_mode_with_balance_kb()
        )







@menu_cmds_router.message(Command("blog"))
async def blog_cmd(message: Message, bot: Bot, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await bot.forward_message(
        chat_id=message.chat.id,
        from_chat_id=-1003540154410,  # ID группы
        message_id=7  # ID сообщения из группы
    )




@menu_cmds_router.message(Command("help"))
async def help_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f" 1. Адрес магазина («Ваш магазин»)"
                         f"\n\n 2. Ответы на частые вопросы (Типовые и по модели коляски пользователя)")



###########################################################################################################
@menu_cmds_router.message(Command("config"))
async def config_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f"1. /quiz_restart - пройти квиз-опрос заново"
                         f"<blockquote>На основании ваших ответов AI-консультант подбирает и сравнивает коляски, "
                         f"соответствующие запросу</blockquote>"
                         f"\n\n/email - указать email для получения чеков"
                         f"<blockquote>При необходимости вы можете указать свой email для получения чеков  об оплате "
                         f"на свою почту</blockquote>"
                         f"\n\n2. Изменить время ТО"
                         f"\n\n3. Сохраненная информация")




# --- 1. Команда /email ---
@menu_cmds_router.message(Command("email"))
async def cmd_email_start(message: Message, state: FSMContext, session: AsyncSession):

    await message.answer(
        "📧 <b>Укажите ваш Email</b> для получения чеков.\n\n"
        "Отправьте адрес электронной почты в ответном сообщении 👇\n"
        "<i>(Или введите /cancel для отмены)</i>"
    )
    await state.set_state(MenuStates.waiting_for_email)


# --- 2. Ловим ввод Email (валидация и сохранение) ---
@menu_cmds_router.message(StateFilter(MenuStates.waiting_for_email))
async def process_email_input(message: Message, state: FSMContext, session: AsyncSession):
    email = message.text.strip().lower()

    # Если пользователь передумал
    if email.lower() == '/cancel':
        await message.answer("Ввод email отменен")
        await state.clear()
        return

    # Проверка формата (Валидация)
    if not re.match(EMAIL_REGEX, email):
        await message.answer(
            "❌ <b>Некорректный формат email</b>\n\n"
            "Пожалуйста, проверьте адрес и попробуйте снова.\n"
            "Пример: <code>example@mail.ru</code>"
        )
        return  # Не сбрасываем состояние, ждем повторного ввода

    # Сохранение в БД
    try:
        await update_user_email(session, message.from_user.id, email)
        await message.answer(f"✅ <b>Email сохранен!</b>"
                             f"\n\nЧеки будут приходить на: <code>{email}</code>"
                             )
        await state.clear()
    except Exception as e:
        await message.answer("Ошибка при сохранении. Попробуйте позже.")
        print(f"Error saving email: {e}")
        await state.clear()



#########################################################################################################


@menu_cmds_router.message(Command("contacts"))
async def contacts_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
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
    if magazine.name == "[Babykea]":
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
    text_offer = (f"1. <a href='https://telegra.ph/Oferta-dlya-chat-bota-Babykea-Bot-Babykea-07-14'>Публичная оферта, "
                  f"Пользовательское соглашение, условия эксплуатации и обслуживания</a>\n\n"
                  f"2. <a href='https://telegra.ph/Politika-konfidencialnosti-07-26-9'>Политика Конфиденциальности</a>")
    await message.answer(text=text_offer, link_preview_options=LinkPreviewOptions(is_disabled=True))




