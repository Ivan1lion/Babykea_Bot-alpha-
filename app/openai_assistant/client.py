from app.openai_assistant.queue import OpenAIRequestQueue


async def ask_assistant(queue: OpenAIRequestQueue, user_id: int, thread_id: str, message: str) -> str:
    return await queue.send(user_id=user_id, thread_id=thread_id, message=message)

