import os
import logging
import aiohttp
import re
import asyncio
from google import genai
from google.genai import types
from openai import AsyncOpenAI

# Настройка логирования
logger = logging.getLogger(__name__)

# === ИНИЦИАЛИЗАЦИЯ КЛИЕНТОВ ===

# 1. OpenAI (Резервный канал)
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 2. Google Gemini (Основной канал)
# Инициализируем клиент один раз.
# Асинхронные методы будут доступны через google_client.aio
google_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


# ==========================================
# 🛠 ФУНКЦИИ ВАЛИДАЦИИ ССЫЛОК (POST-VALIDATION)
# ==========================================

async def check_url_status(session: aiohttp.ClientSession, url: str) -> bool:
    """
    Проверяет доступность ссылки (возвращает True, если статус 200).
    """
    try:
        # Используем метод HEAD (запрашиваем только заголовки, без скачивания всей страницы) - это быстро
        # Но некоторые сайты блокируют HEAD, поэтому надежнее использовать GET с ограничением
        async with session.get(url, timeout=3, allow_redirects=True) as response:
            if response.status == 200:
                return True
            logger.warning(f"❌ Битая ссылка (Status {response.status}): {url}")
            return False
    except Exception as e:
        logger.warning(f"❌ Ошибка проверки ссылки {url}: {e}")
        return False


async def validate_and_fix_links(text: str) -> str:
    """
    Находит все Markdown-ссылки в тексте, проверяет их.
    Если ссылка битая -> убирает URL, оставляя только название.
    """
    # Регулярка для поиска ссылок вида [Текст](https://...)
    # Группа 1: Текст, Группа 2: URL
    link_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)')

    matches = link_pattern.findall(text)
    if not matches:
        return text  # Ссылок нет, возвращаем как есть

    # Собираем уникальные ссылки для проверки
    unique_urls = list(set(url for _, url in matches))

    # Асинхронно проверяем все ссылки разом
    async with aiohttp.ClientSession() as session:
        tasks = [check_url_status(session, url) for url in unique_urls]
        results = await asyncio.gather(*tasks)

    # Создаем карту: URL -> Доступен (True/False)
    url_status = dict(zip(unique_urls, results))

    # Функция замены для re.sub
    def replace_match(match):
        title = match.group(1)
        url = match.group(2)

        if url_status.get(url, False):
            # Ссылка живая - оставляем как есть
            return f"[{title}]({url})"
        else:
            # Ссылка мертвая - оставляем только текст + пометку (или просто текст)
            # Вариант 1: "Anex Air-Z (ссылка не найдена)"
            # Вариант 2 (твой выбор): Просто "Anex Air-Z" (ссылка удаляется)
            return f"{title} (извините ссылка на товар не найдена)"

            # Заменяем все вхождения в тексте

    fixed_text = link_pattern.sub(replace_match, text)
    return fixed_text


# ==========================================
# 🧠 ОСНОВНАЯ ФУНКЦИЯ ЗАПРОСА
# ==========================================

async def ask_responses_api(user_message: str, system_instruction: str) -> str:
    """
    Отправляет запрос к AI.
    Приоритет: Google Gemini 3 Pro -> Fallback: OpenAI.
    В конце выполняется проверка ссылок на валидность.
    """
    raw_answer = ""

    # ---------------------------------------------------------
    #     ПОПЫТКА 1: Google Gemini 3 Pro (Основной)
    # ---------------------------------------------------------
    try:
        # 🔥 Принт для понимания
        print(f"🔔 ПОПЫТКА 1: Google Gemini 3 Pro (Основной)")
        tools_config = [types.Tool(google_search=types.GoogleSearch())]

        generate_config = types.GenerateContentConfig(
            temperature=1.0,
            system_instruction=system_instruction,
            tools=tools_config,
            response_modalities=["TEXT"]  # Явно указываем что отвечать нужно текстом
        )

        # 🔥 ДОБАВЛЕНО: asyncio.wait_for ставит жесткий лимит 60 сек
        # Если Google думает дольше - бросаем ошибку и идем к OpenAI
        response = await asyncio.wait_for(
            google_client.aio.models.generate_content(
                model="gemini-2.0-flash",  # Исправил имя модели на стабильное
                contents=user_message,
                config=generate_config
            ),
            timeout=60.0
        )

        if response.text:
            raw_answer = response.text
        else:
            raise ValueError("Gemini вернул пустой ответ")

    except Exception as e:
        logger.error(f"⚠️ Ошибка Gemini: {e}. Переключаюсь на резерв...", exc_info=True)

        # ---------------------------------------------------------
        # ПОПЫТКА 2: OpenAI ChatGPT (Резерв)
        # ---------------------------------------------------------
        try:
            # 🔥 Принт для понимания
            print(f"🔔 ПОПЫТКА 2: OpenAI ChatGPT (Резерв))")
            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message}
            ]

            response = await openai_client.chat.completions.create(
                model="gpt-5.2",
                messages=messages,
                reasoning={"effort": "high"},
                timeout=60.0  # Таймаут 30 секунд
            )
            raw_answer = response.choices[0].message.content or ""

        except Exception as ex:
            logger.critical(f"❌ CRITICAL: Все API упали: {ex}", exc_info=True)
            return "Извините, технический сбой. Повторите попытку позже."

    # --- 3. ПОСТ-ВАЛИДАЦИЯ ССЫЛОК (LEVEL 3) ---
    if raw_answer:
        # logger.info("🔍 Проверка ссылок на валидность...")
        final_answer = await validate_and_fix_links(raw_answer)
        return final_answer

    return "Не удалось получить ответ."