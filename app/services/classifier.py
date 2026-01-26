import os
from openai import AsyncOpenAI

# Используем OpenAI (gpt-4o-mini или gpt-3.5-turbo) для классификации - это быстрее и дешевле всего
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def classify_intent(user_text: str) -> str:
    """
    Определяет намерение пользователя:
    1. CATALOG - подбор, покупка, наличие, цены.
    2. INFO - сравнение, тренды, 'что лучше', общие вопросы.
    3. SUPPORT - ремонт, запчасти, инструкции, поломки.
    """

    system_prompt = (
        "Ты классификатор намерений для магазина колясок. "
        "Твоя задача — отнести запрос пользователя к одной из трех категорий:\n"
        "1. 'CATALOG' — если пользователь хочет выбрать, купить, узнать цену, наличие или ищет конкретную модель.\n"
        "2. 'INFO' — если пользователь просит СРАВНИТЬ модели (даже если их нет в каталоге), спрашивает про тренды, рейтинги, 'что лучше для зимы' (без контекста покупки у нас).\n"
        "3. 'SUPPORT' — если вопрос про ремонт, поломку, запчасти, как сложить/разобрать, скрипт, стирку.\n\n"
        "В ответ пришли ТОЛЬКО одно слово: CATALOG, INFO или SUPPORT."
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Или gpt-3.5-turbo (самые дешевые)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0,  # Нужна четкость
            max_tokens=10
        )
        intent = response.choices[0].message.content.strip().upper()

        # Страховка, если AI вернет что-то лишнее
        if intent not in ["CATALOG", "INFO", "SUPPORT"]:
            return "CATALOG"  # Дефолт

        return intent

    except Exception:
        return "CATALOG"  # Если ошибка, считаем что это подбор