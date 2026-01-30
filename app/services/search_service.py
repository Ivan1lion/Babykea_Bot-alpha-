import os
import logging
from typing import List, Dict, Optional
from pathlib import Path

import chromadb  # <--- Новая библиотека
from openai import AsyncOpenAI

# from pinecone import Pinecone # <--- Удалено

# Настройка логгера
logger = logging.getLogger(__name__)

# === 1. НАСТРОЙКА ПУТЕЙ И КЛИЕНТОВ ===

# Вычисляем путь к корню проекта.
# Файл лежит в: app/services/search_service.py
# .parent -> app/services
# .parent.parent -> app
# .parent.parent.parent -> корень проекта (где лежит папка chromadb_storage)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chromadb_storage")

# Инициализация OpenAI
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Инициализация ChromaDB
# PersistentClient = база на диске (не в оперативной памяти)
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_or_create_collection(name="strollers")

# === 2. СЛОВАРЬ-ПЕРЕВОДЧИК ===
QUIZ_TRANSLATIONS = {
    # Тип коляски
    "from_birth": "коляска для новорожденного",
    "stroller": "прогулочная коляска для детей от 6 месяцев",
    "service_only": "коляска",

    # Подтип коляски
    "stroller_folds_like_a_cane": "коляска-трость, механизм складывания по типу трость",
    "The_child's_age_is_from_6_months": "механизм складывания по типу книжка",

    # Функционал
    "2in1": "коляска 2 в 1 с люлькой",
    "3in1": "коляска 3 в 1 с автокреслом",
    "transformer": "коляска-трансформер, люлька-трансформер",

    # Сценарий
    "daily_walks": "Для ежедневных прогулок",
    "car_trips": "для удобной перевозки в автомобиле, складывание одной рукой",
    "air_travel": "для путешествий и авиаперелетов, легкая компактная для самолета ручная кладь",

    # Сезон
    "summer": "летняя с вентиляцией",
    "winter": "теплая зимняя непродуваемая (термолюлька), защита ответра",

    # Тип дороги
    "ground": "для езды по грунту, средний размер колес, хорошая амортизация",
    "asphalt": "для езды по асфальту, маневренная городская коляска, легкая",
    "ground and asphalt": "для езды как по асфальту так и по грунту, средний размер колес, хорошая амортизация",
    "offroad and snow": "для езды по бездорожью и снегу, вездеход с большими колёсами и отличной амортизацией",
}


async def get_query_embedding(text: str) -> List[float]:
    """Превращает текст запроса в вектор"""
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Ошибка создания эмбеддинга: {e}")
        return []


def translate_quiz_to_text(quiz_data: dict) -> str:
    """Превращает JSON квиза в поисковую строку на русском."""
    search_terms = []
    for key, value in quiz_data.items():
        if value in QUIZ_TRANSLATIONS:
            search_terms.append(QUIZ_TRANSLATIONS[value])
        elif key in QUIZ_TRANSLATIONS:
            search_terms.append(QUIZ_TRANSLATIONS[key])
        elif isinstance(value, str):
            search_terms.append(value)
    return " ".join(search_terms)


# async def search_products(
#         user_query: str,
#         quiz_json: Optional[dict] = None,
#         magazine_id: Optional[int] = None,
#         top_k: int = 10
# ) -> str:
#     """
#     Главная функция поиска (Адаптировано под ChromaDB).
#     """
#
#     # 1. Формируем "Идеальный поисковый запрос"
#     full_search_text = user_query
#     if quiz_json:
#         translated_quiz = translate_quiz_to_text(quiz_json)
#         full_search_text = f"{full_search_text} {translated_quiz}"
#
#     logger.info(f"🔎 Ищем в ChromaDB по фразе: '{full_search_text}' (Mag ID: {magazine_id})")
#
#     # 2. Получаем вектор
#     vector = await get_query_embedding(full_search_text)
#     if not vector:
#         return ""
#
#     try:
#         # 3. Запрос в базу ChromaDB
#         # Мы запрашиваем чуть больше (top_k * 2), чтобы если Python-фильтр
#         # отсеет чужие магазины, у нас остались варианты.
#         # Если magazine_id нет (поиск по всем) - берем ровно top_k.
#         fetch_k = top_k * 2 if magazine_id else top_k
#
#         results = collection.query(
#             query_embeddings=[vector],
#             n_results=fetch_k
#         )
#
#         # Chroma возвращает структуру: {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}
#         # Проверяем, есть ли результаты
#         if not results['ids'] or not results['ids'][0]:
#             return ""
#
#         # 4. Обработка результатов и фильтрация
#         context_text = ""
#         found_count = 0
#
#         # Данные первого (и единственного) запроса
#         metadatas_list = results['metadatas'][0]
#         distances_list = results['distances'][0]  # Чем меньше, тем лучше (в косинусном расстоянии Chroma)
#
#         for i, meta in enumerate(metadatas_list):
#             if found_count >= top_k:
#                 break
#
#             # --- Python-фильтр по магазину ---
#             # В update_vectors мы сохраняли "magazine_ids_str": "1,2,5"
#             if magazine_id:
#                 allowed_ids_str = meta.get("magazine_ids_str", "")
#                 allowed_ids = allowed_ids_str.split(",")
#                 # Если текущего магазина нет в списке разрешенных для этого товара - пропускаем
#                 if str(magazine_id) not in allowed_ids:
#                     continue
#
#             # Получаем данные
#             name = meta.get('name', 'Без названия')
#             price = meta.get('price', 'Цена не указана')
#             url = meta.get('url', '#')
#             # Обрезаем описание
#             desc = meta.get('description', '')[:3000]
#
#             # 🔥 ВОССТАНОВЛЕНА РЕЛЕВАНТНОСТЬ 🔥
#             # В Chroma чем меньше distance, тем лучше (0 = копия).
#             # Превращаем в % схожести: (1 - distance) * 100
#             dist = distances_list[i]
#             # Защита от отрицательных чисел (если векторы странные), хотя обычно distance <= 1
#             similarity = max(0.0, 1.0 - dist)
#             relevance_percent = int(similarity * 100)
#
#             context_text += (
#                 f"- <b>{name}</b>\n"
#                 f"  Цена: {price} руб.\n"
#                 f"  Ссылка: {url}\n"
#                 f"  Описание: {desc}...\n"
#                 f"  <i>(Релевантность: {relevance_percent}%)</i>\n\n"
#             )
#             found_count += 1
#
#         return context_text
#
#     except Exception as e:
#         logger.error(f"Ошибка поиска в ChromaDB: {e}")
#         return ""



#🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥Для теста релевантности. Вверху рабочая функция🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥
async def search_products(
        user_query: str,
        quiz_json: Optional[dict] = None,
        magazine_id: Optional[int] = None,
        top_k: int = 10
) -> str:
    """
    Главная функция поиска (ChromaDB + Релевантность + PRINT DEBUG).
    """

    # 1. Формируем запрос
    full_search_text = user_query
    if quiz_json:
        translated_quiz = translate_quiz_to_text(quiz_json)
        full_search_text = f"{full_search_text} {translated_quiz}"

    # 🔥 ЗАМЕНИЛИ logger НА print
    print(f"🔎 Ищем в ChromaDB по фразе: '{full_search_text}' (Mag ID: {magazine_id})")

    # 2. Вектор
    vector = await get_query_embedding(full_search_text)
    if not vector:
        return ""

    try:
        # 3. Запрос в базу
        fetch_k = top_k * 2 if magazine_id else top_k

        results = collection.query(
            query_embeddings=[vector],
            n_results=fetch_k
        )

        if not results['ids'] or not results['ids'][0]:
            # 🔥 ЗАМЕНИЛИ logger НА print
            print("⚠️ Ничего не найдено в базе.")
            return ""

        # 4. Обработка результатов
        context_text = ""
        found_count = 0

        metadatas_list = results['metadatas'][0]
        distances_list = results['distances'][0]

        # 🔥 ЗАМЕНИЛИ logger НА print
        print(f"\n--- 📊 РЕЗУЛЬТАТЫ ПОИСКА ({len(metadatas_list)} шт) ---")

        for i, meta in enumerate(metadatas_list):
            if found_count >= top_k:
                break

            # Фильтр по магазину
            if magazine_id:
                allowed_ids_str = meta.get("magazine_ids_str", "")
                allowed_ids = allowed_ids_str.split(",")
                if str(magazine_id) not in allowed_ids:
                    continue

            name = meta.get('name', 'Без названия')
            price = meta.get('price', 'Цена не указана')
            url = meta.get('url', '#')
            desc = meta.get('description', '')[:3000]

            # Расчет релевантности
            dist = distances_list[i]
            similarity = max(0.0, 1.0 - dist)
            relevance_percent = int(similarity * 100)

            # 🔥 ВЫВОД В КОНСОЛЬ ЧЕРЕЗ PRINT
            print(f"[{relevance_percent}%] {name} | {price} руб. | {url}")

            context_text += (
                f"- <b>{name}</b>\n"
                f"  Цена: {price} руб.\n"
                f"  Ссылка: {url}\n"
                f"  Описание: {desc}...\n"
                f"  <i>(Релевантность: {relevance_percent}%)</i>\n\n"
            )
            found_count += 1

        # 🔥 ЗАМЕНИЛИ logger НА print
        print("--------------------------------------------------\n")

        return context_text

    except Exception as e:
        logger.error(f"Ошибка поиска в ChromaDB: {e}")
        return ""