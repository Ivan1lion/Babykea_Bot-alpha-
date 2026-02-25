"""
Точка входа: Telegram-бот + aiohttp (webhook + лендинг оплаты).

Запуск:
  python run_telegram.py           (локально, Windows)
  python -m run_telegram           (Docker)

Docker Compose:
  command: python run_telegram.py
"""

import asyncio
import os
import sys

# Добавляем корень проекта в PYTHONPATH
# (чтобы импорты app.core.* работали при запуске из корня)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import main

if __name__ == "__main__":
    try:
        if os.name == "nt":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass