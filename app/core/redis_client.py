import os
import asyncio
import logging
from redis.asyncio import Redis
from redis.exceptions import RedisError
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)


class SafeRedis:
    """
    Безопасная обёртка над Redis.
    - Не крашит бот если Redis недоступен
    - Отправляет Telegram-уведомление при падении (один раз)
    - Все методы совместимы со старым кодом: get / set / delete
    """

    def __init__(self):
        self._connected = False
        self._alert_sent = False
        self._bot = None
        # Просто создаем объект. Никаких подключений здесь!
        self._client = Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True,
            socket_connect_timeout=1.0, # ⚠️ Увеличил до 1.0 (0.3 мало для Docker)
            socket_timeout=1.0,
            retry_on_timeout=False,
            health_check_interval=0,
        )

    async def connect(self, bot=None):
        """Вызывается из main.py при старте"""
        self._bot = bot
        await self.ping()  # Теперь вызываем без подчеркивания

    async def ping(self):
        """Проверка связи + Сброс флага ошибки (Self-Healing)"""
        try:
            await self._client.ping()
            self._connected = True

            # 🔥 Если Redis ожил, а раньше лежал — сообщаем админу
            if self._alert_sent:
                logger.info("✅ Redis recovered! Alert flag reset.")
                if self._bot:
                    try:
                        admin_id = os.getenv("ADMIN_TELEGRAM_ID")
                        if admin_id:
                            await self._bot.send_message(int(admin_id), "✅ <b>Redis снова доступен!</b>")
                    except Exception:
                        pass

            self._alert_sent = False  # Сбрасываем флаг, чтобы в будущем снова получать алерты
            return True
        except Exception as e:
            self._connected = False
            # Если вызвали connect при старте и сразу ошибка — шлем алерт
            await self._on_error(e)
            return False




    async def _on_error(self, e: Exception):
        self._connected = False
        logger.error(f"Redis error: {e}")

        if self._alert_sent or not self._bot:
            return

        admin_id = os.getenv("ADMIN_TELEGRAM_ID")
        if not admin_id:
            return

        try:
            await self._bot.send_message(
                chat_id=int(admin_id),
                text=(
                    "🚨 <b>Redis недоступен!</b>\n\n"
                    f"Ошибка: <code>{e}</code>\n\n"
                    "Бот работает без кэша."
                ),
                parse_mode="HTML"
            )
            self._alert_sent = True
        except Exception:
            pass

    # -------------------------------------------------------
    # Публичные методы — полная замена стандартного Redis
    # -------------------------------------------------------

    async def get(self, key: str) -> str | None:
        if not self._connected:
            return None
        try:
            val = await self._client.get(key)
            return val
        except (RedisError, Exception) as e:
            await self._on_error(e)
            return None

    async def set(self, key: str, value: str, ex: int = None) -> bool:
        if not self._connected:
            return False
        try:
            await self._client.set(key, value, ex=ex)
            return True
        except (RedisError, Exception) as e:
            await self._on_error(e)
            return False

    async def delete(self, *keys: str) -> int:
        if not self._connected:
            return 0
        try:
            return await self._client.delete(*keys)
        except (RedisError, Exception) as e:
            await self._on_error(e)
            return 0


    ############### Удолить перед деплоем !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    async def keys(self, pattern: str) -> list[str]:
        if not self._connected:
            return []
        try:
            return await self._client.keys(pattern)
        except (RedisError, Exception) as e:
            await self._on_error(e)
            return []
###############################################################################################################


# Создаём глобальный клиент — импортируется везде как раньше
redis_client = SafeRedis()
