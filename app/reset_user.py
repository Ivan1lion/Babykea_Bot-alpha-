import asyncio
from dotenv import load_dotenv

load_dotenv()

# Импортируем твой клиент
from app.core.redis_client import redis_client

# ID пользователя, которого надо обнулить
TARGET_USER_ID = 1887035653


async def main():
    print("🔌 Подключаюсь к Redis...")
    # 🔥 ВАЖНО: Нужно явно подключиться, иначе SafeRedis будет думать, что связи нет
    await redis_client.connect()

    if not redis_client._connected:
        print("❌ Не удалось подключиться к Redis.")
        return

    print(f"🧹 Ищу ключи для пользователя {TARGET_USER_ID}...")

    # Теперь метод keys() существует и сработает
    keys = await redis_client.keys(f"*{TARGET_USER_ID}*")

    if not keys:
        print("✅ Ключи не найдены. Пользователь чист.")
        await redis_client._client.close()  # Закрываем соединение аккуратно
        return

    print(f"Найдено {len(keys)} ключей: {keys}")

    # Удаляем
    await redis_client.delete(*keys)
    print("🗑️ Все ключи удалены!")

    await redis_client._client.close()  # Закрываем соединение


if __name__ == "__main__":
    asyncio.run(main())