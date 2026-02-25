import asyncio
import os
import logging
import xml.etree.ElementTree as ET
import hashlib
from typing import List, Dict
from pathlib import Path
from collections import defaultdict

import aiohttp
import chromadb
from openai import AsyncOpenAI
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
from app.core.db.models import Magazine

# === НАСТРОЙКИ ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# === 🔥 НАСТРОЙКА CHROMA DB ===
# Указываем путь к папке, где будут лежать файлы базы
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chromadb_storage")

# Создаем клиент (PersistentClient сохраняет данные на диск)
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

# Создаем коллекцию (аналог Index в Pinecone)
# metadata={"hnsw:space": "cosine"} говорит базе использовать косинусное сходство (как в Pinecone)
collection = chroma_client.get_or_create_collection(name="strollers", metadata={"hnsw:space": "cosine"})


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
            # Важно: используем raw_description, чтобы не было ошибки имени переменной
            raw_description = offer.findtext("description") or ""
            url = offer.findtext("url")
            price = offer.findtext("price")
            vendor = offer.findtext("vendor") or ""

            # --- Сбор характеристик из тегов <param> ---
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
            full_description = f"Характеристики: {params_str}. Описание: {raw_description}"
            # --- КОНЕЦ БЛОКА ---

            # Текст для Вектора
            full_text_for_search = f"{name} {vendor} {params_str} {raw_description} Цена: {price}".strip()

            if name and url:
                products.append({
                    "id": offer.get("id"),
                    "text": full_text_for_search,
                    "metadata": {
                        "name": name,
                        "url": url,
                        "price": price,
                        # Обрезаем описание до 3000 символов (твой новый лимит)
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
    # Сохраняем ID как строки (Chroma лучше работает со строками в метаданных)
    mag_ids = [str(m.id) for m in magazines]

    # Превращаем список ID в строку "1,2,5"
    mag_ids_str = ",".join(mag_ids)

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

        # === 🔥 ИЗМЕНЕНИЯ ПОД CHROMADB ===
        ids_batch = []
        embeddings_batch = []
        metadatas_batch = []
        documents_batch = []

        url_hash = hashlib.md5(feed_url.encode()).hexdigest()[:10]

        for j, product in enumerate(batch):
            vector_id = f"feed_{url_hash}_{product['id']}"

            meta = product["metadata"]

            # 🔥 ВАЖНОЕ ДОБАВЛЕНИЕ: Сохраняем ссылку-источник
            # Это нужно для manage_chroma.py, чтобы удалять фиды целиком
            meta["source_url"] = feed_url

            # Добавляем ID магазинов (для фильтрации "свой-чужой")
            meta["magazine_ids_str"] = mag_ids_str

            ids_batch.append(vector_id)
            embeddings_batch.append(embeddings[j])
            metadatas_batch.append(meta)
            documents_batch.append(product["text"])

        try:
            # Upsert в Chroma
            collection.upsert(
                ids=ids_batch,
                embeddings=embeddings_batch,
                metadatas=metadatas_batch,
                documents=documents_batch
            )
            logger.info(f"✅ Группа {mag_names}: загружено {len(ids_batch)} товаров...")
        except Exception as e:
            logger.error(f"Ошибка ChromaDB Upsert: {e}")

    logger.info(f"🎉 Группа {mag_names} полностью обновлена!")




async def run_update_cycle():
    """Один полный цикл обновления"""
    logger.info("🚀 Начинаем обновление базы товаров (ChromaDB)...")

    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db_session:
        result = await db_session.execute(select(Magazine))
        all_magazines = result.scalars().all()

        feed_groups = defaultdict(list)
        for mag in all_magazines:
            raw_url = mag.feed_url
            if raw_url and raw_url.strip() != "Google_Search":
                clean_url = raw_url.strip()
                feed_groups[clean_url].append(mag)
            else:
                logger.info(f"⏭ Магазин {mag.name} пропущен")

        async with aiohttp.ClientSession() as http_session:
            for feed_url, mags_in_group in feed_groups.items():
                await process_feed_group(http_session, feed_url, mags_in_group)

    await engine.dispose()
    logger.info("🏁 Обновление базы ChromaDB завершено.")


if __name__ == "__main__":
    asyncio.run(run_update_cycle())