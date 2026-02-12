import os
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import closed_menu
from app.redis_client import redis_client

help_router = Router()
logger = logging.getLogger(__name__)


tech_channel_id = int(os.getenv("TECH_CHANNEL_ID"))



# ---  КОНФИГУРАЦИЯ ---
# Ключ: Команда
# Значение: Словарь с ключом для Redis и ID сообщения в канале
FAQ_CONFIG = {
    "/faq_wheels_remove": {
        "redis_key": "media:faq_wheels_remove",
        "msg_id": 15  # 👈 Замените на реальный ID сообщения в канале
    },
    "/faq_wheels_pump": {
        "redis_key": "media:faq_wheels_pump",
        "msg_id": 16
    },
    "/faq_squeak": {
        "redis_key": "media:faq_squeak",
        "msg_id": 17
    },
}


# --- 1. Основное меню /help ---
@help_router.message(Command("help"))
async def help_cmd(message: Message, session: AsyncSession):
    if await closed_menu(message=message, session=session):
        return

    # Текст сообщения
    text = (
        "<b>🆘 Центр поддержки</b>\n\n"
        "<b>1. Ответы на самые частые вопросы:</b>\n"
        "Нажмите на команду, чтобы посмотреть видео:\n\n"
        "/faq_wheels_remove - Как снять колёса?\n"
        "/faq_wheels_pump - Как накачать колёса?\n"
        "/faq_squeak - Коляска скрипит. Мне продали брак?\n\n"

        "<b>2. Умный помощник</b>\n"
        "Если у вас другой вопрос, попробуйте решить его с AI-консультантом:\n"
        "/mode_info - нажмите для обращения к AI\n\n"

        "<b>3. Связь с мастером</b>\n"
        "Если AI-консультант не помог, напишите мне в личку."
    )

    # Кнопка связи с мастером
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать мастеру", url="https://t.me/YOUR_USERNAME")]
    ])

    await message.answer(text, reply_markup=kb)



# --- 2. Умный обработчик (Lazy Loading) ---
@help_router.message(F.text.in_(FAQ_CONFIG.keys()))
async def send_faq_video(message: Message, session: AsyncSession):
    if await closed_menu(message=message, session=session):
        return

    command = message.text
    config = FAQ_CONFIG.get(command)

    redis_key = config["redis_key"]
    channel_msg_id = config["msg_id"]

    try:
        # 1. Сначала ищем быстрый file_id в Redis
        cached_file_id = await redis_client.get(redis_key)

        if cached_file_id:
            # 🚀 ВАРИАНТ А: Видео есть в кэше -> Отправляем быстро
            await message.answer_video(
                video=cached_file_id,
                caption=f"📹 Видео-ответ по запросу: {command}"
            )
            return

        # 🐢 ВАРИАНТ Б: В кэше пусто (или рестарт) -> Берем из канала
        print(f"🔄 Кэш пуст для {command}. Копирую из канала...")

        # Копируем сообщение из канала юзеру
        sent_msg = await message.bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=tech_channel_id,
            message_id=channel_msg_id,
            caption=f"📹 Видео-ответ по запросу: {command}"
        )

        # 🔥 САМОЕ ВАЖНОЕ: Сохраняем свежий file_id в Redis на будущее
        # Проверяем, что это видео, и берем самый качественный вариант (-1)
        if sent_msg.video:
            new_file_id = sent_msg.video.file_id
            # Сохраняем в Redis (можно навечно, или на месяц)
            await redis_client.set(redis_key, new_file_id)
            print(f"✅ Новый file_id сохранен в Redis: {redis_key}")

        elif sent_msg.video_note:
            new_file_id = sent_msg.video_note.file_id
            await redis_client.set(redis_key, new_file_id)

    except Exception as e:
        logger.error(f"❌ Ошибка Lazy Loading: {e}")
        await message.answer("Извините, видео временно недоступно.")