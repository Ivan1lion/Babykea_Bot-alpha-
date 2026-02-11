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


# async def validate_and_fix_links(text: str) -> str:
#     """
#     Находит все Markdown-ссылки в тексте, проверяет их.
#     Если ссылка битая -> убирает URL, оставляя только название.
#     """
#     # Регулярка для поиска ссылок вида [Текст](https://...)
#     # Группа 1: Текст, Группа 2: URL
#     link_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)')
#
#     matches = link_pattern.findall(text)
#     if not matches:
#         return text  # Ссылок нет, возвращаем как есть
#
#     # Собираем уникальные ссылки для проверки
#     unique_urls = list(set(url for _, url in matches))
#
#     # Асинхронно проверяем все ссылки разом
#     async with aiohttp.ClientSession() as session:
#         tasks = [check_url_status(session, url) for url in unique_urls]
#         results = await asyncio.gather(*tasks)
#
#     # Создаем карту: URL -> Доступен (True/False)
#     url_status = dict(zip(unique_urls, results))
#
#     # Функция замены для re.sub
#     def replace_match(match):
#         title = match.group(1)
#         url = match.group(2)
#
#         if url_status.get(url, False):
#             # Ссылка живая - оставляем как есть
#             return f"[{title}]({url})"
#         else:
#             # Ссылка мертвая - оставляем только текст + пометку (или просто текст)
#             # Вариант 1: "Anex Air-Z (ссылка не найдена)"
#             # Вариант 2 (твой выбор): Просто "Anex Air-Z" (ссылка удаляется)
#             return f"{title} (извините ссылка на товар не найдена)"
#
#             # Заменяем все вхождения в тексте
#
#     fixed_text = link_pattern.sub(replace_match, text)
#     return fixed_text

async def validate_and_fix_links(text: str) -> str:
    """
    Находит HTML-ссылки <a href="...">Текст</a>, проверяет их.
    Если ссылка битая -> убирает тег <a>, оставляя только текст + пометку.
    """
    # 1. Регулярка для HTML ссылок
    # Группа 1: URL, Группа 2: Текст внутри тега
    link_pattern = re.compile(r'<a\s+href=[\'"](https?://[^\'"]+)[\'"][^>]*>(.*?)</a>', re.IGNORECASE)

    matches = link_pattern.findall(text)
    if not matches:
        return text

    # Собираем уникальные ссылки (URL - это первая группа)
    unique_urls = list(set(url for url, _ in matches))

    # Асинхронно проверяем
    async with aiohttp.ClientSession() as session:
        tasks = [check_url_status(session, url) for url in unique_urls]
        results = await asyncio.gather(*tasks)

    url_status = dict(zip(unique_urls, results))

    def replace_match(match):
        url = match.group(1)   # URL
        title = match.group(2) # Текст ссылки (например, название коляски)

        if url_status.get(url, False):
            # Ссылка живая - возвращаем как было
            return f'<a href="{url}">{title}</a>'
        else:
            # Ссылка мертвая - убираем тег, оставляем текст
            return f'{title} (ссылка не найдена)'

    fixed_text = link_pattern.sub(replace_match, text)
    return fixed_text




def clean_markdown_artifacts(text: str) -> str:
    """
    🔥 Очищает текст:
    1. Превращает Markdown (**жирный**) в HTML.
    2. Удаляет ВСЕ теги, кроме разрешенных Telegram-ом.
    """
    if not text:
        return ""

    # --- ЭТАП 1: Обработка Markdown ---

    # Жирный: **текст** -> <b>текст</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

    # Заголовки: ## Текст -> <b>Текст</b>
    text = re.sub(r'#{2,}\s*(.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # Списки: * или - в начале строки -> •
    text = re.sub(r'^\s*[\*\-]\s+', '• ', text, flags=re.MULTILINE)

    # --- ЭТАП 2: Умная очистка HTML (Белый список) ---

    # Список тегов, которые поддерживает Telegram
    ALLOWED_TAGS = {
        'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del',
        'a', 'code', 'pre', 'blockquote'
    }

    def clean_tag(match):
        full_tag = match.group(0)  # Весь тег целиком: <div class="x">
        tag_name = match.group(2).lower()  # Имя тега: div

        # 1. Исключения для читаемости:
        # <br> и </p> заменяем на перенос строки, иначе слова склеятся
        if tag_name == 'br':
            return '\n'
        if tag_name == 'p' and full_tag.startswith('</'):  # Закрывающий </p>
            return '\n'
        if tag_name == 'hr':  # Разделитель превращаем в линию
            return '〰️〰️〰️〰️〰️\n'

        # 2. Если тег в белом списке — оставляем как есть
        if tag_name in ALLOWED_TAGS:
            return full_tag

        # 3. Если тег неизвестен Telegram — УДАЛЯЕМ ЕГО (возвращаем пустоту)
        return ''

    # Регулярка ищет любые теги: </?tagName...>
    # Группа 1: Слэш (если есть)
    # Группа 2: Имя тега
    # Группа 3: Атрибуты и остальное
    text = re.sub(r'<(/?)(\w+)([^>]*)>', clean_tag, text)

    # Чистим двойные переносы, которые могли возникнуть
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text




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
                model="gemini-3-flash-preview",
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
                timeout=60.0  # Таймаут 60 секунд
            )
            raw_answer = response.choices[0].message.content or ""

        except Exception as ex:
            logger.critical(f"❌ CRITICAL: Все API упали: {ex}", exc_info=True)
            return "Извините, технический сбой. Повторите попытку позже."

    # --- 3. ПОСТ-ВАЛИДАЦИЯ ССЫЛОК (LEVEL 3) ---
    if raw_answer:
        # 1. 🔥 Сначала чистим от Markdown-артефактов (звездочек)
        clean_answer = clean_markdown_artifacts(raw_answer)

        # 2. Потом проверяем HTML-ссылки на валидность в уже чистом тексте
        final_answer = await validate_and_fix_links(clean_answer)

        return final_answer

    return "Не удалось получить ответ."