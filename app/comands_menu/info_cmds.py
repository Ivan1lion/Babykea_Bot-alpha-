import os
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import closed_menu


logger = logging.getLogger(__name__)
info_router = Router()


tech_channel_id = int(os.getenv("TECH_CHANNEL_ID"))


@info_router.message(Command("guide"))
async def what_cmd(message: Message, session: AsyncSession):
    if await closed_menu(message=message, session=session):
        return
    # 1. Пытаемся отправить мгновенно через Redis (PRO способ)
    # Мы ищем file_id, который сохранили под именем "intro_video"
    video_id = await redis_client.get("media:guide_video")

    if video_id:
        try:
            await message.answer_video(
                video=video_note_id,
                caption=f"📝 <b>Шпаргалка: Что нужно учитывать при подборе</b>"
                        f"\n\n• Тип коляски (от рождения или прогулка)"
                        f"\n• Функционал (2в1, 3в1 или просто люлька)"
                        f"\n• Формат использования (для прогулок или путешествий)"
                        f"\n• Сезон (зима или лето)"
                        f"\n• Тип дороги (грунт, асфальт или бездорожье)"
                        f"\n👆 Эти вопросы мы закрыли в самом начале, когда вы проходили квиз. Это база для поиска."
                        f"\n• "
                        f"\n• Дизайн (внешний вид коляски должен радовать маму 😍)"
            )
            print(f"🔔 ПОПЫТКА 1: Redis)")
            return  # Успех, выходим
        except Exception as e:
            logger.error(f"Ошибка отправки video_note из Redis: {e}")

    # 2. FALLBACK 1: Если в Redis пусто, пробуем copy_message (Старый способ)
    # Это страховка на случай, если ты забыл загрузить видео в тех.канал
    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=tech_channel_id,  # ID тех канала
            message_id=28,  # ID сообщения из группы
            reply_markup=kb.quiz_start
        )
        print(f"🔔 ПОПЫТКА 2: Пересылка из канала)")
        return
    except Exception:
        pass  # Идем к самому надежному варианту

    # 3. FALLBACK 2: Если всё сломалось — файл с диска (Железобетонный вариант)
    # ВАЖНО: answer_video отправляет ПРЯМОУГОЛЬНИК.
    # Если нужен КРУЖОК с диска, используй answer_video_note (но файл должен быть квадратным 1:1)
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        # Убедись, что путь правильный
        VIDEO_PATH = os.path.join(BASE_DIR, "..", "mediafile_for_bot", "video.mp4")
        video_file = FSInputFile(VIDEO_PATH)

        # Если файл на диске - это обычное видео, используй answer_video
        await message.answer_video(
            video=video_file,
            supports_streaming=True,
            reply_markup=kb.quiz_start
        )
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Не удалось отправить приветствие: {e}")
        # Хотя бы текст отправим, чтобы бот не молчал
        await message.answer("Добро пожаловать!", reply_markup=kb.quiz_start)


    await message.answer(f" 1. Карусель видеороликов о нюансах подбора детской коляски"
                         f"\n\n 2. Квиз по подбору типа коляски"
                         f"\n\n 3. Тригер про AI с призывам сделать запрос")




@info_router.message(Command("rules"))
async def where_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о правилах правильной эксплуатации"
                         f"\n\n 2. Призыв перейти в раздел '💊 Как продлить жизнь коляске'")




@info_router.message(Command("service"))
async def when_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f" 1. Карусель видеороликов о ТО детской коляски"
                         f"\n\n 2. Запуск времени до планового ТО")