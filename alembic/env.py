import asyncio
from logging.config import fileConfig
import os
import sys

# 🔥 Импортируем dotenv для чтения файла .env
from dotenv import load_dotenv, find_dotenv

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# --- НАСТРОЙКА ПУТЕЙ И ИМПОРТ МОДЕЛЕЙ ---
# Добавляем корневую папку в пути, чтобы видеть app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.core.db.models import Base

# ------------------------------------------

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# --- 🔥 ФУНКЦИЯ ПОЛУЧЕНИЯ URL ---
def get_db_url():
    load_dotenv(find_dotenv())  # Ищем и загружаем .env

    # 1. Пробуем взять готовый DB_URL
    url = os.getenv("DB_URL")

    # 2. Если нет, собираем из частей
    if not url:
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        db = os.getenv("POSTGRES_DB", "postgres")
        host = "localhost"  # Локально это localhost
        port = os.getenv("DB_PORT", "5432")
        url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    # Отладка: выводим URL в консоль (скрывая пароль), чтобы ты видел, что он загрузился
    # print(f"DEBUG: Using DB URL: {url.split('@')[-1]}")
    return url


# --------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_db_url()  # Получаем URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.
    """

    # 1. Получаем конфигурацию из alembic.ini
    configuration = config.get_section(config.config_ini_section)
    if not configuration:
        configuration = {}

    # 2. 🔥 ВРУЧНУЮ добавляем URL в словарь настроек
    # Это решает проблему KeyError: 'url'
    db_url = get_db_url()
    configuration["sqlalchemy.url"] = db_url

    connectable = async_engine_from_config(
        configuration,  # Передаем словарь, в котором УЖЕ есть URL
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()