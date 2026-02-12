import os
import asyncio
from aiogram import Bot
from aiogram.types import FSInputFile
from dotenv import find_dotenv, load_dotenv

# Загружаем переменные
load_dotenv(find_dotenv())

API_TOKEN = os.getenv("TOKEN")
# 🔥 Берем из env, чтобы было единообразно с основным ботом
TECH_CHANNEL_ID = int(os.getenv("TECH_CHANNEL_ID") )

# Небольшая защита от дурака
if not TECH_CHANNEL_ID:
     raise ValueError("Не указан TECH_CHANNEL_ID в .env")


MEDIA_FOLDER = "mediafile_for_bot"


async def upload_photos():
    bot = Bot(token=API_TOKEN)

    # Получаем список файлов
    if not os.path.exists(MEDIA_FOLDER):
        print(f"❌ Папка {MEDIA_FOLDER} не найдена!")
        return

    files = [f for f in os.listdir(MEDIA_FOLDER) if os.path.isfile(os.path.join(MEDIA_FOLDER, f))]
    file_ids = {}

    print(f"Найдено файлов: {len(files)}. Начинаю загрузку в канал {TECH_CHANNEL_ID}...\n")

    for file_name in files:
        file_path = os.path.join(MEDIA_FOLDER, file_name)
        try:
            media = FSInputFile(file_path)

            # 🔥 ИЗМЕНЕНИЕ: Отправляем в КАНАЛ, а не в личку
            msg = await bot.send_photo(
                chat_id=TECH_CHANNEL_ID,
                photo=media,
                caption=f"File: {file_name}"
            )

            # Получаем file_id самого большого размера
            file_id = msg.photo[-1].file_id
            file_ids[file_name] = file_id

            print(f"✅ Загружен: {file_name}")

            # Небольшая задержка, чтобы не поймать FloodWait (если фото много)
            await asyncio.sleep(4)

        except Exception as e:
            print(f"❌ Ошибка при загрузке {file_name}: {e}")

    await bot.session.close()

    print("\n" + "=" * 30)
    print("ГОТОВЫЙ СЛОВАРЬ ДЛЯ КОНФИГА:")
    print("=" * 30)

    # Выводим в формате Python-словаря
    print("UPLOADED_PHOTOS = {")
    for name, fid in file_ids.items():
        print(f'    "{name}": "{fid}",')
    print("}")


if __name__ == "__main__":
    asyncio.run(upload_photos())





















# import os
# import asyncio
# from aiogram import Bot, types
# from aiogram.types import FSInputFile
# from dotenv import find_dotenv, load_dotenv
#
# load_dotenv(find_dotenv())
#
#
#
# API_TOKEN = os.getenv("TOKEN")
# if not API_TOKEN:
#     raise ValueError("Переменная окружения TOKEN не установлена!")
#
# MEDIA_FOLDER = "mediafile_for_bot"  # папка с фото/видео
#
# async def upload_photos():
#     bot = Bot(token=API_TOKEN)
#
#     files = [f for f in os.listdir(MEDIA_FOLDER) if os.path.isfile(os.path.join(MEDIA_FOLDER, f))]
#     file_ids = {}
#
#     for file_name in files:
#         file_path = os.path.join(MEDIA_FOLDER, file_name)
#         try:
#             media = FSInputFile(file_path)
#             # Отправляем себе (можно свой ID или ADMIN_ID)
#             msg = await bot.send_photo(chat_id="1887035653", photo=media, caption=file_name)
#             file_id = msg.photo[-1].file_id
#             file_ids[file_name] = file_id
#             print(f"{file_name} -> {file_id}")
#         except Exception as e:
#             print(f"Ошибка при загрузке {file_name}: {e}")
#
#     await bot.session.close()
#
#     print("\nСписок file_id для QUIZ_CONFIG:")
#     for name, fid in file_ids.items():
#         print(f'"{name}": "{fid}",')
#
# if __name__ == "__main__":
#     asyncio.run(upload_photos())