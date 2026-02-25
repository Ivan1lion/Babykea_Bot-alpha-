"""
Обработчик Callback API от VK.

VK шлёт POST на /vk/callback с JSON:
  {"type": "confirmation", "group_id": 123}        → отвечаем строкой подтверждения
  {"type": "message_new", "object": {...}, ...}     → обрабатываем сообщение
  {"type": "message_event", "object": {...}, ...}   → обрабатываем нажатие кнопки

Маршрут регистрируется в run_vk.py через aiohttp.
"""

import json
import logging
from aiohttp import web

from app.platforms.vk.bot import VK_SECRET, VK_CONFIRMATION_CODE, VK_GROUP_ID

logger = logging.getLogger(__name__)


async def vk_callback_handler(request: web.Request) -> web.Response:
    """
    Единая точка входа для всех событий VK Callback API.

    VK требует:
      - Ответить "ok" на каждое событие (иначе будет повторять)
      - На "confirmation" — ответить строкой подтверждения
      - Проверить secret если задан
    """
    try:
        data = await request.json()
    except Exception:
        return web.Response(text="bad json", status=400)

    event_type = data.get("type")
    group_id = data.get("group_id")

    # Проверка group_id
    if group_id and int(group_id) != VK_GROUP_ID:
        return web.Response(text="wrong group", status=403)

    # Проверка секретного ключа
    if VK_SECRET:
        if data.get("secret") != VK_SECRET:
            logger.warning(f"VK callback: wrong secret from {request.remote}")
            return web.Response(text="forbidden", status=403)

    # === CONFIRMATION (подтверждение сервера) ===
    if event_type == "confirmation":
        return web.Response(text=VK_CONFIRMATION_CODE)

    # === MESSAGE_NEW (новое сообщение от юзера) ===
    if event_type == "message_new":
        from app.platforms.vk.handlers.user_handlers import handle_message_new
        obj = data.get("object", {}).get("message", {})
        if obj:
            # Запускаем обработку асинхронно, чтобы не задерживать ответ VK
            import asyncio
            vk_api = request.app.get("vk_api")
            session_maker = request.app.get("session_maker")
            asyncio.create_task(
                _safe_handle(handle_message_new, obj, vk_api, session_maker)
            )
        return web.Response(text="ok")

    # === MESSAGE_EVENT (нажатие inline-кнопки с callback) ===
    if event_type == "message_event":
        from app.platforms.vk.handlers.user_handlers import handle_message_event
        obj = data.get("object", {})
        if obj:
            import asyncio
            vk_api = request.app.get("vk_api")
            session_maker = request.app.get("session_maker")
            asyncio.create_task(
                _safe_handle(handle_message_event, obj, vk_api, session_maker)
            )
        return web.Response(text="ok")

    # === WALL_POST_NEW (новый пост в группе — для рассылки) ===
    if event_type == "wall_post_new":
        from app.platforms.vk.posting.vk_broadcaster import handle_wall_post_new
        obj = data.get("object", {})
        if obj:
            import asyncio
            vk_api = request.app.get("vk_api")
            session_maker = request.app.get("session_maker")
            asyncio.create_task(
                _safe_handle(handle_wall_post_new, obj, vk_api, session_maker)
            )
        return web.Response(text="ok")

    # Все остальные события — просто "ok"
    return web.Response(text="ok")


async def _safe_handle(handler, *args):
    """Обёртка для безопасного вызова хэндлера в create_task."""
    try:
        await handler(*args)
    except Exception as e:
        logger.exception(f"VK handler error: {e}")
