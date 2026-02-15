import json
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from app.schemas import UserCache
from app.redis_client import redis_client

USER_TTL = 300  # Время жизни кэша (5 мин)


async def get_user_cached(session: AsyncSession, telegram_id: int) -> UserCache | None:
    """
    1. Ищет в Redis.
    2. Если нет — ищет в БД, сохраняет в Redis и возвращает.
    """
    redis_key = f"user:{telegram_id}"

    # 1. Пробуем достать из Redis
    raw_data = await redis_client.get(redis_key)
    if raw_data:
        # ✅ Вернули из кэша (БД не трогаем)
        return UserCache(**json.loads(raw_data))

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
    await redis_client.set(redis_key, user_dto.model_dump_json(), ex=USER_TTL)

    return user_dto


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
        # 2. Инвалидируем (удаляем) старый кэш, чтобы при следующем запросе подтянулись свежие данные
        # (просто удаляем, пусть следующий get сам сходит в базу):
        await redis_client.delete(f"user:{telegram_id}")


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
    await redis_client.delete(f"user:{telegram_id}")

