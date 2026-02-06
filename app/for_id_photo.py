import os
import asyncio
from aiogram import Bot, types
from aiogram.types import FSInputFile
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


API_TOKEN = os.getenv("TOKEN")
if not API_TOKEN:
    raise ValueError("Переменная окружения TOKEN не установлена!")

MEDIA_FOLDER = "mediafile_for_bot"  # папка с фото/видео

async def upload_photos():
    bot = Bot(token=API_TOKEN)

    files = [f for f in os.listdir(MEDIA_FOLDER) if os.path.isfile(os.path.join(MEDIA_FOLDER, f))]
    file_ids = {}

    for file_name in files:
        file_path = os.path.join(MEDIA_FOLDER, file_name)
        try:
            media = FSInputFile(file_path)
            # Отправляем себе (можно свой ID или ADMIN_ID)
            msg = await bot.send_photo(chat_id="1887035653", photo=media, caption=file_name)
            file_id = msg.photo[-1].file_id
            file_ids[file_name] = file_id
            print(f"{file_name} -> {file_id}")
        except Exception as e:
            print(f"Ошибка при загрузке {file_name}: {e}")

    await bot.session.close()

    print("\nСписок file_id для QUIZ_CONFIG:")
    for name, fid in file_ids.items():
        print(f'"{name}": "{fid}",')

if __name__ == "__main__":
    asyncio.run(upload_photos())