from openai import AsyncOpenAI
import os

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = (
    "Ты эксперт по подбору детских колясок. "
    "Отвечай подробно и по делу, только по запросу пользователя."
)

async def ask_responses_api(user_message: str) -> str:
    """
    Отправка запроса в Responses API без контекста
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]
    response = await openai_client.responses.create(
        model="gpt-5.2",
        temperature=0.7,
        top_p=0.9,
        input=messages,
    )
    return response.output_text
