import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import text # 👈 Нам понадобится text для чистого SQL

# 1. Загружаем переменные
load_dotenv()


from app.db.config import engine
from app.db.models import Base

# Важно: Импортируй ВСЕ модели, чтобы Base о них знал перед удалением/созданием
from app.db.models import User, Magazine, MagazineChannel, MyChannel, TechChannel, Payment, UserQuizProfile


async def main():
    print("🧨 НАЧИНАЕМ ПОЛНЫЙ СБРОС БАЗЫ ДАННЫХ (CASCADE)...")

    async with engine.begin() as conn:
        # --- ШАГ 1: УДАЛЕНИЕ ---
        # Вместо попыток удалить таблицы по одной, мы сносим схему public целиком.
        # CASCADE удалит всё: таблицы, связи, типы данных и "призраков".
        print("🗑 Удаляю схему public...")
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        # (Если у вас пользователь не 'postgres', возможно, grant не нужен или нужен другой)

        print("✅ Схема полностью очищена.")

        # --- ШАГ 2: СОЗДАНИЕ (Опционально, можно через Alembic) ---
        # Если вы хотите сразу создать новые таблицы без миграций, раскомментируйте:
        print("🏗 Создаю новые таблицы...")
        await conn.run_sync(Base.metadata.create_all)

    print("✨ ГОТОВО! База девственно чиста.")


# if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())