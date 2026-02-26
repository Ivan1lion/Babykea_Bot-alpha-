"""
Сервис пользователя. Кэш Redis, резервирование запросов, обновление флагов.

Мультиплатформенный: работает и с telegram_id, и с vk_id.
Принцип: все функции принимают platform_id + platform, 
а внутри определяют нужный фильтр по User.telegram_id или User.vk_id.
"""

import json
import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.models import User
from app.core.schemas import UserCache
from app.core.redis_client import redis_client


logger = logging.getLogger(__name__)
USER_TTL = 300  # Время жизни кэша (5 мин)


def _user_filter(platform_id: int, platform: str = "telegram"):
    """Возвращает SQLAlchemy фильтр для поиска юзера по платформе."""
    if platform == "vk":
        return User.vk_id == platform_id
    return User.telegram_id == platform_id


def _cache_key(platform_id: int, platform: str = "telegram") -> str:
    """Ключ Redis для кэша юзера."""
    if platform == "vk":
        return f"user:vk:{platform_id}"
    return f"user:{platform_id}"


async def get_user_cached(
    session: AsyncSession,
    platform_id: int,
    platform: str = "telegram",
) -> UserCache | None:
    """
    1. Ищет в Redis.
    2. Если нет — ищет в БД, сохраняет в Redis и возвращает.
    """
    redis_key = _cache_key(platform_id, platform)

    # 1. Пробуем достать из Redis
    raw_data = await redis_client.get(redis_key)
    if raw_data:
        return UserCache(**json.loads(raw_data))

    # 2. Если в кэше нет — идем в БД
    result = await session.execute(
        select(User).where(_user_filter(platform_id, platform))
    )
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
    await redis_client.set(redis_key, user_dto.model_dump_json(), ex=USER_TTL)
    logger.debug(f"💾 Cached user {platform}:{platform_id} for {USER_TTL}s")

    return user_dto


async def try_reserve_request(
    session: AsyncSession,
    platform_id: int,
    platform: str = "telegram",
) -> bool:
    """
    Атомарно резервирует 1 запрос прямо в БД.

    Использует UPDATE ... WHERE requests_left > 0 — PostgreSQL гарантирует,
    что при одновременных вызовах только один из них пройдёт успешно.

    Возвращает True если запрос успешно зарезервирован, False если баланс исчерпан.
    """
    stmt = (
        update(User)
        .where(
            _user_filter(platform_id, platform),
            User.requests_left > 0
        )
        .values(requests_left=User.requests_left - 1)
        .returning(User.id)
    )
    result = await session.execute(stmt)
    await session.commit()

    reserved = result.scalar_one_or_none()

    if reserved:
        await redis_client.delete(_cache_key(platform_id, platform))
        logger.debug(f"✅ Request reserved for {platform}:{platform_id}")
        return True

    logger.debug(f"❌ Reserve failed (balance = 0) for {platform}:{platform_id}")
    return False


async def refund_request(platform_id: int, platform: str = "telegram"):
    """
    Возвращает 1 запрос юзеру при ошибке LLM.
    Использует собственную сессию — вызывается из except-блока фоновой задачи.
    """
    from app.core.db.config import session_maker
    try:
        async with session_maker() as session:
            stmt = (
                update(User)
                .where(_user_filter(platform_id, platform))
                .values(requests_left=User.requests_left + 1)
            )
            await session.execute(stmt)
            await session.commit()
            await redis_client.delete(_cache_key(platform_id, platform))
            logger.info(f"↩️ Refund: вернули 1 запрос юзеру {platform}:{platform_id}")
    except Exception as e:
        logger.error(f"❌ Refund failed для юзера {platform}:{platform_id}: {e}")


async def update_user_requests(
    session: AsyncSession,
    platform_id: int,
    decrement: int = 1,
    platform: str = "telegram",
):
    """
    Списывает баланс. Обновляет И базу, И кэш.
    """
    stmt = (
        update(User)
        .where(_user_filter(platform_id, platform))
        .values(requests_left=User.requests_left - decrement)
        .returning(User)
    )
    result = await session.execute(stmt)
    updated_user = result.scalar_one_or_none()
    await session.commit()

    if updated_user:
        await redis_client.delete(_cache_key(platform_id, platform))
        logger.debug(f"🗑️ Invalidated cache for {platform}:{platform_id}")


async def update_user_flags(
    session: AsyncSession,
    platform_id: int,
    platform: str = "telegram",
    **kwargs,
):
    """
    Универсальная функция для обновления флагов.
    """
    stmt = (
        update(User)
        .where(_user_filter(platform_id, platform))
        .values(**kwargs)
        .returning(User)
    )
    await session.execute(stmt)
    await session.commit()

    await redis_client.delete(_cache_key(platform_id, platform))
    logger.debug(f"🗑️ Invalidated cache for {platform}:{platform_id}")
