import os
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

from app.db.models import User

logger = logging.getLogger(__name__)

# Настройки рассылки (через сколько дней слать и ID сообщений в тех-канале)
tech_channel_id = int(os.getenv("TECH_CHANNEL_ID"))


# SERVICE_STAGES = {
#     0: {"days": 3, "msg_id": 105},  # 0 уровень -> ждет 3 дня -> шлем msg_id 101 -> переход на ур. 1
#     1: {"days": 89, "msg_id": 105},  # 1 уровень -> ждет 89 дней -> шлем msg_id 102 -> переход на ур. 2
#     2: {"days": 178, "msg_id": 105}  # 2 уровень -> ждет 178 дней -> шлем msg_id 103 -> переход на ур. 3
# }
SERVICE_STAGES = {
    0: {"seconds": 10, "msg_id": 105}, # 10 секунд
    1: {"seconds": 20, "msg_id": 105}, # 20 секунд
    2: {"seconds": 30, "msg_id": 105}  # 30 секунд
}

# Максимальная задержка при рестарте воркера (5 минут)
_MAX_RESTART_DELAY = 300


async def _service_notifications_loop(bot: Bot, session_maker):
    """Внутренний цикл воркера. Выполняет одну итерацию проверки и уведомлений."""
    while True:
        try:
            now = datetime.now(timezone.utc)

            async with session_maker() as session:
                stmt = select(User).where(
                    User.is_active == True,
                    User.service_registered_at.is_not(None),
                    User.service_level < 3
                )
                result = await session.execute(stmt)
                users = result.scalars().all()

                for user in users:
                    stage = SERVICE_STAGES.get(user.service_level)
                    if not stage:
                        continue

                    # target_date = user.service_registered_at + timedelta(days=stage["days"])
                    target_date = user.service_registered_at + timedelta(seconds=stage["seconds"])

                    if now >= target_date:
                        try:
                            if user.service_level == 0:
                                feedback_kb = InlineKeyboardMarkup(inline_keyboard=[
                                    [
                                        InlineKeyboardButton(text="👍", callback_data="to_feed_like"),
                                        InlineKeyboardButton(text="👎", callback_data="to_feed_dislike")
                                    ]
                                ])

                                await bot.copy_message(
                                    chat_id=user.telegram_id,
                                    from_chat_id=tech_channel_id,
                                    message_id=stage["msg_id"],
                                    reply_markup=feedback_kb,
                                    caption="\u200b"
                                )

                            else:
                                await bot.copy_message(
                                    chat_id=user.telegram_id,
                                    from_chat_id=tech_channel_id,
                                    message_id=stage["msg_id"],
                                    caption="🛠 Пришло время планового обслуживания вашей коляски!"
                                )

                            user.service_level += 1
                            await session.commit()

                            await asyncio.sleep(0.5)

                        except TelegramForbiddenError:
                            user.is_active = False
                            await session.commit()
                            logger.info(f"Юзер {user.telegram_id} заблокировал бота. Деактивирован.")
                        except TelegramBadRequest as e:
                            logger.error(f"Ошибка TelegramBadRequest: {e}")
                        except Exception as e:
                            logger.error(f"Непредвиденная ошибка при отправке ТО: {e}")

        except Exception as e:
            # Пробрасываем наружу — внешний цикл перехватит и перезапустит воркер
            raise

        # await asyncio.sleep(86400)
        await asyncio.sleep(5)


async def run_service_notifications(bot: Bot, session_maker):
    """
    Обёртка с автоматическим перезапуском воркера при падении.
    Использует экспоненциальную задержку: 5с -> 10с -> 20с -> ... -> 300с (5 мин).
    После 5 минут ожидания сбрасывается на 5с снова.
    """
    restart_delay = 5  # Начальная задержка перезапуска в секундах

    while True:
        try:
            logger.info("⚙️ Запущен фоновый воркер планового ТО...")
            restart_delay = 5  # Сбрасываем задержку при успешном старте
            await _service_notifications_loop(bot, session_maker)

        except asyncio.CancelledError:
            # Бот останавливается штатно — выходим без перезапуска
            logger.info("🛑 Воркер ТО остановлен штатно.")
            return

        except Exception as e:
            logger.error(
                f"💥 Воркер ТО упал с ошибкой: {e}. "
                f"Перезапуск через {restart_delay} сек...",
                exc_info=True
            )
            await asyncio.sleep(restart_delay)

            # Экспоненциальный backoff: удваиваем задержку, но не больше _MAX_RESTART_DELAY
            restart_delay = min(restart_delay * 2, _MAX_RESTART_DELAY)