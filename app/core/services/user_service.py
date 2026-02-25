import json
import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.models import User
from app.core.schemas import UserCache
from app.core.redis_client import redis_client


logger = logging.getLogger(__name__)
USER_TTL = 300  # Время жизни кэша (5 мин)


async def get_user_cached(session: AsyncSession, telegram_id: int) -> UserCache | None:
    """
    1. Ищет в Redis.
    2. Если нет — ищет в БД, сохраняет в Redis и возвращает.
    """
    redis_key = f"user:{telegram_id}"

    # 1. Пробуем достать из Redis
    # --- БЕЗОПАСНОЕ ЧТЕНИЕ ИЗ REDIS ---
    raw_data = await redis_client.get(redis_key)
    if raw_data:
        return UserCache(**json.loads(raw_data))  # ← Нашли в кэше — сразу возвращаем
    # ----------------------------------

    # 2. Если в кэше нет — идем в БД
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user_db = result.scalar_one_or_none()

    if not user_db:
        return None

    # Превращаем модель БД в Pydantic схему
    user_dto = UserCache(
        id=user_db.id,
        telegram_id=user_db.telegram_id,
        username=user_db.username,
        promo_code=user_db.promo_code,
        magazine_id=user_db.magazine_id,
        requests_left=user_db.requests_left,
        is_active=user_db.is_active,
        closed_menu_flag=user_db.closed_menu_flag,
        first_catalog_request=user_db.first_catalog_request,
        first_info_request=user_db.first_info_request,
        show_intro_message=user_db.show_intro_message
    )

    # 3. Сохраняем в Redis
    # --- БЕЗОПАСНАЯ ЗАПИСЬ В REDIS ---
    await redis_client.set(redis_key, user_dto.model_dump_json(), ex=USER_TTL)
    logger.debug(f"💾 Cached user {telegram_id} for {USER_TTL}s")
    # ----------------------------------

    return user_dto




async def try_reserve_request(session: AsyncSession, telegram_id: int) -> bool:
    """
    Атомарно резервирует 1 запрос прямо в БД.

    Использует UPDATE ... WHERE requests_left > 0 — PostgreSQL гарантирует,
    что при одновременных вызовах только один из них пройдёт успешно.

    Возвращает True если запрос успешно зарезервирован, False если баланс исчерпан.
    Вызывать ДО запуска фоновой задачи, чтобы исключить race condition.
    """
    stmt = (
        update(User)
        .where(
            User.telegram_id == telegram_id,
            User.requests_left > 0  # Атомарная защита от гонки
        )
        .values(requests_left=User.requests_left - 1)
        .returning(User.id)
    )
    result = await session.execute(stmt)
    await session.commit()

    reserved = result.scalar_one_or_none()

    if reserved:
        # Инвалидируем кэш — старый баланс больше неактуален
        await redis_client.delete(f"user:{telegram_id}")
        logger.debug(f"✅ Request reserved for user {telegram_id}")
        return True

    logger.debug(f"❌ Reserve failed (balance = 0) for user {telegram_id}")
    return False


async def refund_request(telegram_id: int):
    """
    Возвращает 1 запрос юзеру при ошибке LLM.
    Использует собственную сессию — вызывается из except-блока фоновой задачи,
    где оригинальная сессия уже могла быть закрыта или в невалидном состоянии.
    """
    from app.core.db.config import session_maker  # Локальный импорт во избежание циклов
    try:
        async with session_maker() as session:
            stmt = (
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(requests_left=User.requests_left + 1)
            )
            await session.execute(stmt)
            await session.commit()
            await redis_client.delete(f"user:{telegram_id}")
            logger.info(f"↩️ Refund: вернули 1 запрос юзеру {telegram_id}")
    except Exception as e:
        logger.error(f"❌ Refund failed для юзера {telegram_id}: {e}")





async def update_user_requests(session: AsyncSession, telegram_id: int, decrement: int = 1):
    """
    Списывает баланс. Обновляет И базу, И кэш.
    """
    # 1. Обновляем БД
    # Используем returning, чтобы сразу получить актуальное значение
    stmt = (
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(requests_left=User.requests_left - decrement)
        .returning(User)
    )
    result = await session.execute(stmt)
    updated_user = result.scalar_one_or_none()

    # Важно: вызывающий код должен сделать session.commit(), либо делаем тут:
    await session.commit()

    if updated_user:
        # 2. Инвалидируем (удаляем) старый кэш
        # --- БЕЗОПАСНАЯ ИНВАЛИДАЦИЯ ---
        await redis_client.delete(f"user:{telegram_id}")
        logger.debug(f"🗑️ Invalidated cache for user {telegram_id}")
        # -------------------------------


async def update_user_flags(session: AsyncSession, telegram_id: int, **kwargs):
    """
    Универсальная функция для обновления флагов (например, first_catalog_request=False)
    """
    stmt = (
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(**kwargs)
        .returning(User)
    )
    await session.execute(stmt)
    await session.commit()

    # Сбрасываем кэш
    # --- БЕЗОПАСНАЯ ИНВАЛИДАЦИЯ ---
    await redis_client.delete(f"user:{telegram_id}")
    logger.debug(f"🗑️ Invalidated cache for user {telegram_id}")
    # -------------------------------

