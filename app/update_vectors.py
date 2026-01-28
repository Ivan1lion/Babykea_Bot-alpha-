import asyncio
import os
import logging
import xml.etree.ElementTree as ET
import hashlib
from typing import List, Dict
from pathlib import Path
from collections import defaultdict

import aiohttp
from openai import AsyncOpenAI
from pinecone import Pinecone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from dotenv import load_dotenv

# === ЗАГРУЗКА ПЕРЕМЕННЫХ ===
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DB_URL")
if not DATABASE_URL:
    DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(f"❌ Ошибка: Не найдена переменная DB_URL в {env_path}")

if "sqlite" in DATABASE_URL and "aiosqlite" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")

import sys

sys.path.append(str(BASE_DIR))
from app.db.models import Magazine

# === НАСТРОЙКИ ===
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "strollers-index")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)


async def download_feed(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(url, timeout=60) as response:
            if response.status == 200:
                return await response.text()
            else:
                logger.error(f"Ошибка скачивания фида {url}: Status {response.status}")
                return None
    except Exception as e:
        logger.error(f"Ошибка соединения с {url}: {e}")
        return None


def parse_offers_from_xml(xml_content: str) -> List[Dict]:
    products = []
    try:
        root = ET.fromstring(xml_content)
        for offer in root.findall(".//offer"):
            available = offer.get("available")
            if available == "false":
                continue

            name = offer.findtext("name") or offer.findtext("model")
            raw_description = offer.findtext("description") or ""
            url = offer.findtext("url")
            price = offer.findtext("price")
            vendor = offer.findtext("vendor") or ""

            # --- 🔥 НОВОЕ: Сбор характеристик из тегов <param> ---
            params_list = []
            for param in offer.findall("param"):
                p_name = param.get("name")
                p_value = param.text
                if p_name and p_value:
                    params_list.append(f"{p_name}: {p_value}")

            # Собираем строку характеристик
            params_str = "; ".join(params_list)

            # Формируем "Умное описание" для AI
            # Сначала факты (параметры), потом лирика (описание)
            # AI (Gemini) обожает структурированные данные в начале.
            full_description = f"Характеристики: {params_str}. Описание: {raw_description}"
            # --- КОНЕЦ БЛОКА ---

            # Текст для Вектора (OpenAI Embeddings)
            # Теперь поиск будет находить "легкую коляску", потому что "Вес: 10кг" есть в векторе
            full_text_for_search = f"{name} {vendor} {params_str} {raw_description} Цена: {price}".strip()

            if name and url:
                products.append({
                    "id": offer.get("id"),
                    "text": full_text_for_search,
                    "metadata": {
                        "name": name,
                        "url": url,
                        "price": price,
                        # Обрезаем описание товара до 3000 символов
                        "description": full_description[:3000]
                    }
                })
    except Exception as e:
        logger.error(f"Ошибка парсинга XML: {e}")

    return products


async def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        return [data.embedding for data in response.data]
    except Exception as e:
        logger.error(f"Ошибка OpenAI Embeddings: {e}")
        return []


async def process_feed_group(session: aiohttp.ClientSession, feed_url: str, magazines: List[Magazine]):
    mag_names = [m.name for m in magazines]
    # 🔥 ИСПРАВЛЕНИЕ: Pinecone требует список СТРОК, а не чисел
    mag_ids = [str(m.id) for m in magazines]

    logger.info(f"🔄 Обработка группы магазинов: {mag_names}")

    xml_content = await download_feed(session, feed_url)
    if not xml_content: return

    products = parse_offers_from_xml(xml_content)
    logger.info(f"📦 В фиде найдено товаров: {len(products)}")

    if not products: return

    batch_size = 100
    for i in range(0, len(products), batch_size):
        batch = products[i: i + batch_size]
        texts_to_embed = [p["text"] for p in batch]
        embeddings = await get_embeddings_batch(texts_to_embed)

        if not embeddings: continue

        vectors_to_upsert = []
        url_hash = hashlib.md5(feed_url.encode()).hexdigest()[:10]

        for j, product in enumerate(batch):
            vector_id = f"feed_{url_hash}_{product['id']}"
            metadata = product["metadata"]
            metadata["magazine_ids"] = mag_ids  # Список ID

            vectors_to_upsert.append({
                "id": vector_id,
                "values": embeddings[j],
                "metadata": metadata
            })

        try:
            index.upsert(vectors=vectors_to_upsert)
            logger.info(f"✅ Группа {mag_names}: загружено {len(vectors_to_upsert)} товаров...")
        except Exception as e:
            logger.error(f"Ошибка Pinecone Upsert: {e}")

    logger.info(f"🎉 Группа {mag_names} полностью обновлена!")


async def run_update_cycle():
    """Один полный цикл обновления"""
    logger.info("🚀 Начинаем обновление базы товаров...")

    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db_session:
        result = await db_session.execute(select(Magazine))
        all_magazines = result.scalars().all()

        feed_groups = defaultdict(list)
        for mag in all_magazines:
            raw_url = mag.feed_url
            # Проверяем, что URL есть и это не Google_Search
            if raw_url and raw_url.strip() != "Google_Search":
                # 🔥 ГЛАВНОЕ ИЗМЕНЕНИЕ: Удаляем пробелы по краям
                clean_url = raw_url.strip()
                # Группируем по чистой ссылке
                feed_groups[clean_url].append(mag)
            else:
                logger.info(f"⏭ Магазин {mag.name} пропущен")

        async with aiohttp.ClientSession() as http_session:
            for feed_url, mags_in_group in feed_groups.items():
                await process_feed_group(http_session, feed_url, mags_in_group)

    await engine.dispose()
    logger.info("🏁 Обновление базы завершено.")


if __name__ == "__main__":
    # Просто запускаем один раз и выходим
    asyncio.run(run_update_cycle())














#import asyncio
# import os
# import logging
# import xml.etree.ElementTree as ET
# from typing import List, Dict
# from pathlib import Path
#
# import aiohttp
# from openai import AsyncOpenAI
# from pinecone import Pinecone, ServerlessSpec
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
# from dotenv import load_dotenv
#
# # === ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
# # 1. Находим путь к файлу .env (он на уровень выше папки app)
# BASE_DIR = Path(__file__).resolve().parent.parent
# env_path = BASE_DIR / ".env"
#
# # 2. Загружаем переменные именно из этого файла
# load_dotenv(dotenv_path=env_path)
#
# # === ПРОВЕРКА ===
# DATABASE_URL = os.getenv("DB_URL")
# if not DATABASE_URL:
#     raise ValueError(f"❌ Ошибка: Не найдена переменная DATABASE_URL. Убедись, что она есть в файле {env_path}")
#
# # Если используется SQLite, нужно убедиться, что драйвер асинхронный
# if "sqlite" in DATABASE_URL and "aiosqlite" not in DATABASE_URL:
#     # Автоматически исправляем sqlite:// на sqlite+aiosqlite://
#     DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
#
# # Импортируем твои модели
# # (Чтобы Python увидел папку app, иногда нужно добавить ее в путь, но попробуем пока так)
# import sys
# sys.path.append(str(BASE_DIR)) # Добавляем корень проекта в пути поиска
# from app.db.models import Magazine, Base
#
#
# load_dotenv()
# # === НАСТРОЙКИ ===
# # Сюда подтянутся данные из .env файла
# PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "strollers-index")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# # Строка подключения к твоей БД (как в основном боте)
# DATABASE_URL = os.getenv("DB_URL")
#
# # Настройка логирования (чтобы видеть процесс в консоли)
# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
# logger = logging.getLogger(__name__)
#
# # Инициализация клиентов
# openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
# pc = Pinecone(api_key=PINECONE_API_KEY)
# index = pc.Index(PINECONE_INDEX_NAME)
#
#
# async def download_feed(session: aiohttp.ClientSession, url: str) -> str:
#     """Скачивает YML/XML файл магазина"""
#     try:
#         async with session.get(url, timeout=60) as response:
#             if response.status == 200:
#                 return await response.text()
#             else:
#                 logger.error(f"Ошибка скачивания фида {url}: Status {response.status}")
#                 return None
#     except Exception as e:
#         logger.error(f"Ошибка соединения с {url}: {e}")
#         return None
#
#
# def parse_offers_from_xml(xml_content: str) -> List[Dict]:
#     """Разбирает XML и достает товары (Название, Описание, Ссылка, Цена)"""
#     products = []
#     try:
#         root = ET.fromstring(xml_content)
#         # В YML товары обычно лежат в shop -> offers -> offer
#         # Ищем все теги 'offer'
#         for offer in root.findall(".//offer"):
#             # Проверяем наличие (available="true")
#             available = offer.get("available")
#             if available == "false":
#                 continue
#
#             name = offer.findtext("name") or offer.findtext("model")
#             description = offer.findtext("description") or ""
#             url = offer.findtext("url")
#             price = offer.findtext("price")
#
#             # Собираем текст для вектора: Название + Описание + Цена
#             # Это то, по чему ИИ будет искать "смысл"
#             full_text_for_search = f"{name} {description} Цена: {price}".strip()
#
#             if name and url:
#                 products.append({
#                     "id": offer.get("id"),  # ID товара в магазине
#                     "text": full_text_for_search,  # Текст для эмбеддинга
#                     "metadata": {
#                         "name": name,
#                         "url": url,
#                         "price": price,
#                         "description": description[:1000]  # Обрезаем слишком длинные
#                     }
#                 })
#     except Exception as e:
#         logger.error(f"Ошибка парсинга XML: {e}")
#
#     return products
#
#
# async def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
#     """Превращает список текстов в список векторов (Batching)"""
#     try:
#         # text-embedding-3-small - дешевая и быстрая модель
#         response = await openai_client.embeddings.create(
#             model="text-embedding-3-small",
#             input=texts
#         )
#         # Возвращаем список векторов
#         return [data.embedding for data in response.data]
#     except Exception as e:
#         logger.error(f"Ошибка OpenAI Embeddings: {e}")
#         return []
#
#
# async def process_magazine(session: aiohttp.ClientSession, magazine: Magazine):
#     """Полный цикл обработки одного магазина"""
#     # БЫЛО: magazine.title -> СТАЛО: magazine.name
#     logger.info(f"🔄 Обработка магазина: {magazine.name} (ID: {magazine.id})")
#
#     if not magazine.feed_url:
#         # БЫЛО: magazine.title -> СТАЛО: magazine.name
#         logger.info(f"⚠️ У магазина {magazine.name} нет YML-фида. Пропускаем.")
#         return
#
#     # 1. Скачиваем
#     xml_content = await download_feed(session, magazine.feed_url)
#     if not xml_content:
#         return
#
#     # 2. Парсим
#     products = parse_offers_from_xml(xml_content)
#     logger.info(f"📦 Найдено товаров: {len(products)}")
#
#     if not products:
#         return
#
#     # 3. Генерируем векторы и грузим в Pinecone ПАЧКАМИ по 100 штук
#     batch_size = 100
#
#     for i in range(0, len(products), batch_size):
#         batch = products[i: i + batch_size]
#
#         # Подготовка текстов для OpenAI
#         texts_to_embed = [p["text"] for p in batch]
#
#         # Получаем векторы
#         embeddings = await get_embeddings_batch(texts_to_embed)
#
#         if not embeddings:
#             continue
#
#         # Подготовка данных для Pinecone
#         vectors_to_upsert = []
#         for j, product in enumerate(batch):
#             vector_id = f"mag_{magazine.id}_{product['id']}"
#
#             metadata = product["metadata"]
#             metadata["magazine_id"] = magazine.id
#
#             vectors_to_upsert.append({
#                 "id": vector_id,
#                 "values": embeddings[j],
#                 "metadata": metadata
#             })
#
#         # Загрузка в Pinecone
#         try:
#             index.upsert(vectors=vectors_to_upsert)
#             logger.info(f"✅ Загружено {len(vectors_to_upsert)} товаров...")
#         except Exception as e:
#             logger.error(f"Ошибка Pinecone Upsert: {e}")
#
#     # БЫЛО: magazine.title -> СТАЛО: magazine.name
#     logger.info(f"🎉 Магазин {magazine.name} полностью загружен!")
#
#
# async def main():
#     # Настройка подключения к БД (SQLite или PostgreSQL - возьмет из URL)
#     engine = create_async_engine(DATABASE_URL)
#     async_session = async_sessionmaker(engine, expire_on_commit=False)
#
#     async with aiohttp.ClientSession() as http_session:
#         async with async_session() as db_session:
#             # Получаем все магазины
#             result = await db_session.execute(select(Magazine))
#             magazines = result.scalars().all()
#
#             for magazine in magazines:
#                 await process_magazine(http_session, magazine)
#
#     await engine.dispose()
#     logger.info("🏁 Обновление базы завершено.")
#
#
# if __name__ == "__main__":
#     # Запуск скрипта
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         pass