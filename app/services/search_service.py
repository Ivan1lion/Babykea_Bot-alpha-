import os
import logging
from typing import List, Dict, Optional
from openai import AsyncOpenAI
from pinecone import Pinecone

# Настройка логгера
logger = logging.getLogger(__name__)

# Инициализация клиентов (они возьмут ключи из переменных окружения)
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME", "strollers-index")
pinecone_index = pc.Index(index_name)

# === 1. СЛОВАРЬ-ПЕРЕВОДЧИК (ИЗ ТЕХНИЧЕСКОГО В ЧЕЛОВЕЧЕСКИЙ) ===
# Здесь мы превращаем сухие ключи квиза в богатые поисковые фразы
QUIZ_TRANSLATIONS = {
    # Тип коляски
    "from_birth": "коляска для новорожденного",
    "stroller": "прогулочная коляска для детей от 6 месяцев",
    "service_only": "коляска",

    # Подтип коляски (subtype)
    "stroller_folds_like_a_cane": "коляска-трость",
    "The_child's_age_is_from_6_months": "прогулочная коляска для детей от 6 месяцев",
    
    # Функционал коляски
    "2in1": "коляска 2 в 1 с люлькой",
    "3in1": "коляска 3 в 1 с автокреслом",
    "transformer": "коляска-трансформер",

    # Сценарий использования (usage_format)
    "daily_walks": "Для ежедневных прогулок",
    "car_trips": "для удобной перевозки в автомобиле, складывание одной рукой",
    "air_travel": "для путешествий и авиаперелетов, легкая компактная для самолета ручная кладь",

    # Сезон
    "summer": "летняя с вентиляцией",
    "winter": "теплая зимняя непродуваемая (термолюлька)",

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
    """
    Превращает JSON квиза в поисковую строку на русском.
    Пример: {"usage_format": "air_travel"} -> "легкая компактная коляска для самолета ручная кладь"
    """
    search_terms = []

    # Проходимся по ключам и значениям JSON
    for key, value in quiz_data.items():
        # Если само значение есть в словаре (например "air_travel")
        if value in QUIZ_TRANSLATIONS:
            search_terms.append(QUIZ_TRANSLATIONS[value])

        # Если ключ есть в словаре (на всякий случай)
        elif key in QUIZ_TRANSLATIONS:
            search_terms.append(QUIZ_TRANSLATIONS[key])

        # Если это просто текст (например, пользователь ввел что-то руками)
        elif isinstance(value, str):
            search_terms.append(value)

    return " ".join(search_terms)


async def search_in_pinecone(
        user_query: str,
        quiz_json: Optional[dict] = None,
        magazine_id: Optional[int] = None,
        top_k: int = 10
) -> str:
    """
    Главная функция поиска.
    1. Объединяет запрос юзера и данные квиза.
    2. Ищет в Pinecone подходящие товары.
    3. Возвращает готовый текстовый блок для промпта AI.
    """

    # 1. Формируем "Идеальный поисковый запрос"
    full_search_text = user_query

    if quiz_json:
        translated_quiz = translate_quiz_to_text(quiz_json)
        # Объединяем: "Хочу красную" + "легкая для самолета"
        full_search_text = f"{full_search_text} {translated_quiz}"

    logger.info(f"🔎 Ищем в Pinecone по фразе: '{full_search_text}' (Mag ID: {magazine_id})")

    # 2. Получаем вектор
    vector = await get_query_embedding(full_search_text)
    if not vector:
        return ""

    # 3. Фильтр по магазину (ВАЖНО!)
    # Если magazine_id передан, ищем ТОЛЬКО в этом магазине.
    # Если нет (например, платный юзер), фильтр будет пустой (ищем везде).
    metadata_filter = {}
    if magazine_id:
        # Pinecone "магия": оператор $eq ищет значение ВНУТРИ списка.
        metadata_filter = {"magazine_ids": {"$eq": str(magazine_id)}}

    try:
        # 4. Запрос в базу
        results = pinecone_index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            filter=metadata_filter if magazine_id else None
        )

        if not results['matches']:
            return ""

        # 5. Формируем красивый текст для AI
        context_text = ""

        for match in results['matches']:
            meta = match['metadata']
            score = match['score']

            # Безопасное получение данных (чтобы не было ошибок None)
            name = meta.get('name', 'Без названия')
            price = meta.get('price', 'Цена не указана')
            url = meta.get('url', '#')
            desc = meta.get('description', '')[:1000]  # Обрезаем текст описания для AI

            # Превращаем 0.89123 в 89%
            relevance_percent = int(score * 100)

            # Формируем блок для AI.
            # Мы специально пишем "Релевантность", чтобы AI понимал вес товара.
            context_text += (
                f"- <b>{name}</b>\n"
                f"  Цена: {price} руб.\n"
                f"  Ссылка: {url}\n"
                f"  Описание: {desc}...\n"
                f"  <i>(Релевантность: {relevance_percent}%)</i>\n\n"
            )

        return context_text

    except Exception as e:
        logger.error(f"Ошибка поиска в Pinecone: {e}")
        return ""