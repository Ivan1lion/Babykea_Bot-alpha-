from aiogram import Router
from .standard_cmds import standard_router
from .crud_cmds import crud_router
from .info_cmds import info_router
from .ai_cmds import ai_router

# Создаем главный роутер меню
menu_cmds_router = Router()

# Подключаем дочерние роутеры
menu_cmds_router.include_router(standard_router)
menu_cmds_router.include_router(crud_router)
menu_cmds_router.include_router(info_router)
menu_cmds_router.include_router(ai_router)

# Экспортируем для использования в main.py
__all__ = ["menu_cmds_router"]


# app/comands_menu/
# ├── __init__.py           # 👈 Точка сборки всех роутеров
# ├── standard_cmds.py      # Простые ответы (/help, /offer, /what, /where...)
# ├── crud_cmds.py       # Личный кабинет: /config, /email (FSM)
# ├── info_cmds.py          # Логика первых 3 кнопок: /what, /where, /when
# └── ai_cmds.py            # Сложная логика: /ai_consultant
