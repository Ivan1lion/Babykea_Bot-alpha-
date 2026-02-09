import asyncio
from dotenv import load_dotenv

load_dotenv()

from app.redis_client import redis_client

# ID пользователя, которого надо обнулить
TARGET_USER_ID = 1887035653


async def main():
    print(f"🧹 Ищу ключи для пользователя {TARGET_USER_ID}...")

    # Ищем все ключи, где встречается этот ID
    # Шаблон *ID* находит и fsm:bot:ID:ID:data и любые другие
    keys = await redis_client.keys(f"*{TARGET_USER_ID}*")

    if not keys:
        print("✅ Ключи не найдены. Пользователь чист.")
        return

    print(f"Найдено {len(keys)} ключей: {keys}")

    # Удаляем
    await redis_client.delete(*keys)
    print("🗑️ Все ключи удалены!")


if __name__ == "__main__":
    asyncio.run(main())