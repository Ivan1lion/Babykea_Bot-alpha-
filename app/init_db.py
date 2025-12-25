import asyncio

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

from app.db.config import create_db, drop_db


async def init_db():
    await drop_db() # удаление Базы Данных
    await create_db() # создание Базы Данных

if __name__ == "__main__":
    asyncio.run(init_db())
