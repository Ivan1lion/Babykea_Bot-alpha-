from aiogram import Router
from .standard_cmds import standard_router
from .crud_cmds import crud_router
from .info_cmds import info_router
from .ai_cmds import ai_router
from .help_cmds import help_router

# Создаем главный роутер меню
menu_cmds_router = Router()

# Подключаем дочерние роутеры
menu_cmds_router.include_router(standard_router)
menu_cmds_router.include_router(crud_router)
menu_cmds_router.include_router(info_router)
menu_cmds_router.include_router(ai_router)
menu_cmds_router.include_router(help_router)

# Экспортируем для использования в main.py
__all__ = ["menu_cmds_router"]