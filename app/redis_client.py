import os
from redis.asyncio import Redis
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Создаем объект Redis здесь, чтобы импортировать его везде
redis_client = Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True  # Важно: получаем строки, а не байты
)