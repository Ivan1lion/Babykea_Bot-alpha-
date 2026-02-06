import logging
from aiogram.types import Message
from app.redis_client import redis_client

logger = logging.getLogger(__name__)


async def cache_media_from_post(message: Message):
    """
    Сохраняет file_id медиа-файла в Redis.
    Ключ берется из CAPTION (подписи) к посту.
    Пример: Постишь видео с подписью 'intro_video' -> в Redis летит 'media:intro_video' = 'file_id'
    """
    if not message.caption:
        return  # Нет подписи - не знаем как назвать этот файл

    # Очищаем подпись от пробелов и делаем маленькими буквами для надежности
    key_name = message.caption.strip()
    redis_key = f"media:{key_name}"

    file_id = None

    # Определяем тип медиа
    if message.video:
        file_id = message.video.file_id
    elif message.photo:
        # Берем последнее фото (оно самое качественное)
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.animation:
        file_id = message.animation.file_id
    elif message.voice:
        file_id = message.voice.file_id

    if file_id:
        # Сохраняем навечно (или пока не перезапишем новым постом)
        await redis_client.set(redis_key, file_id)
        logger.info(f"✅ MEDIA CACHED: {redis_key} -> {file_id}")
    else:
        logger.warning(f"⚠️ Пост в тех.канале с подписью '{key_name}', но без медиа-файла.")