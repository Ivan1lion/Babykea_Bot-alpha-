import os
import logging
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


async def ask_responses_api(user_message: str, system_instruction: str) -> str:
    """
    Отправляет запрос к AI.
    Приоритет: Google Gemini 3 Pro (с поиском) -> Fallback: OpenAI (ChatGPT).

    Args:
        user_message (str): Вопрос пользователя.
        system_instruction (str): Полный системный промпт (с данными квиза и URL).
    """

    # ---------------------------------------------------------
    # ПОПЫТКА 1: Google Gemini 3 Pro (Основной)
    # ---------------------------------------------------------
    try:
        # Настраиваем инструмент поиска (Grounding)
        # В Gemini 3 модель сама решает, когда гуглить (Dynamic Retrieval)
        tools_config = [
            types.Tool(google_search=types.GoogleSearch())
        ]

        # Конфигурация генерации
        generate_config = types.GenerateContentConfig(
            temperature=1.0,  # Рекомендовано Google для Gemini 3
            system_instruction=system_instruction,
            tools=tools_config
        )

        # logger.info("🚀 Запрос к Gemini 3 Pro (Async)...")

        # ИСПОЛЬЗУЕМ native async (через .aio)
        # Модель: gemini-3-pro-preview (так как у тебя теперь платный аккаунт)
        response = await google_client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=user_message,
            config=generate_config
        )

        if response.text:
            return response.text
        else:
            raise ValueError("Gemini вернул пустой текстовый ответ")

    except Exception as e:
        # Логируем ошибку, но не роняем бота
        logger.error(f"⚠️ Ошибка Gemini API: {e}. Переключаюсь на резерв (ChatGPT)...", exc_info=True)

    # ---------------------------------------------------------
    # ПОПЫТКА 2: OpenAI ChatGPT (Резерв)
    # ---------------------------------------------------------
    try:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_message}
        ]

        # Используем твою модель (замени gpt-5.2 на gpt-4o, если 5.2 еще нет в API)
        response = await openai_client.chat.completions.create(
            model="gpt-5.2",
            messages=messages,
            temperature=0.7,
            top_p=0.9,
        )

        answer = response.choices[0].message.content
        if not answer:
            raise ValueError("ChatGPT вернул пустой ответ")

        return answer

    except Exception as e:
        logger.critical(f"❌ CRITICAL: Оба API недоступны: {e}", exc_info=True)
        return (
            "Извините, сейчас наблюдаются технические проблемы с подключением к нейросетям. "
            "Пожалуйста, повторите ваш запрос через пару минут."
        )

















# from openai import AsyncOpenAI
# import os
#
# openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#
# SYSTEM_PROMPT = (
#     "Ты эксперт по подбору детских колясок. "
#     "Отвечай подробно и по делу, только по запросу пользователя."
# )
#
# async def ask_responses_api(user_message: str) -> str:
#     """
#     Отправка запроса в Responses API без контекста
#     """
#     messages = [
#         {"role": "system", "content": SYSTEM_PROMPT},
#         {"role": "user", "content": user_message}
#     ]
#     response = await openai_client.responses.create(
#         model="gpt-5.2",
#         temperature=0.7,
#         top_p=0.9,
#         input=messages,
#     )
#     return response.output_text
