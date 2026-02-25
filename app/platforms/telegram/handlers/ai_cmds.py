import os
import asyncio
import logging
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.db.models import User
from app.core.db.crud import closed_menu
import app.platforms.telegram.keyboards as kb
from app.core.redis_client import redis_client
from app.core.services.user_service import get_user_cached, update_user_flags


ai_router = Router()
logger = logging.getLogger(__name__)

tech_channel_id = int(os.getenv("TECH_CHANNEL_ID"))
ai_post = int(os.getenv("AI_POST"))


@ai_router.message(Command("ai_consultant"))
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
        # Мы ищем file_id, который сохранили под именем "ai_video"
        video_note_id = await redis_client.get("media:ai_video")

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
                from_chat_id=tech_channel_id,  # ID группы
                message_id=ai_post,  # ID сообщения из группы
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