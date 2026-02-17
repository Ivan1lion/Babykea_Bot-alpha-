import logging
from aiogram.types import Message
from app.redis_client import redis_client

logger = logging.getLogger(__name__)


async def cache_media_from_post(message: Message):
    """
    Сохраняет file_id медиа-файла в Redis.
    Работает в двух режимах:
    1. Прямой пост с подписью (для фото/видео).
    2. РЕПЛАЙ (ОТВЕТ) текстом на медиа (для кружочков).
    """

    key_name = None
    file_id = None

    # --- СЦЕНАРИЙ 1: Реплай (Ответ) на сообщение ---
    # (Идеально для кружочков, у которых нет подписи)
    if message.reply_to_message and message.text:
        key_name = message.text.strip()  # Имя ключа берем из текста ответа (например "intro_video")
        media_msg = message.reply_to_message  # А файл ищем в том сообщении, на которое ответили

        if media_msg.video_note:
            file_id = media_msg.video_note.file_id
        elif media_msg.video:
            file_id = media_msg.video.file_id
        elif media_msg.photo:
            file_id = media_msg.photo[-1].file_id
        elif media_msg.document:
            file_id = media_msg.document.file_id
        elif media_msg.voice:
            file_id = media_msg.voice.file_id

    # --- СЦЕНАРИЙ 2: Обычный пост с подписью ---
    # (Работает для обычных видео и картинок)
    elif message.caption:
        key_name = message.caption.strip()

        if message.video:
            file_id = message.video.file_id
        elif message.photo:
            file_id = message.photo[-1].file_id
        elif message.document:
            file_id = message.document.file_id
        elif message.animation:
            file_id = message.animation.file_id
        elif message.voice:
            file_id = message.voice.file_id

    # --- СОХРАНЕНИЕ ---
    if key_name and file_id:
        # Приводим ключ к нижнему регистру для надежности
        redis_key = f"media:{key_name}"

        # Сохраняем в Redis
        await redis_client.set(redis_key, file_id)
        logger.info(f"✅ MEDIA CACHED: {redis_key} -> {file_id}")

        # (Опционально) Можем отправить реакцию или ответ, чтобы ты видел, что бот "съел" файл
        try:
            await message.react([{"type": "emoji", "emoji": "nm"}])  # Ставит реакцию "ОК" (если бот админ)
        except:
            pass

    elif key_name and not file_id:
        logger.warning(f"⚠️ Попытка сохранить '{key_name}', но медиа-файл не найден.")