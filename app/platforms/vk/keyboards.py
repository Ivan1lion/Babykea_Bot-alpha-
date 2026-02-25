"""
VK-клавиатуры.

VK использует JSON-объект Keyboard вместо InlineKeyboardMarkup.
Два типа:
  - Обычная (keyboard) — появляется внизу чата
  - Inline (inline=True) — прикрепляется к сообщению (аналог Telegram inline)
"""

import json
from vkbottle import Keyboard, KeyboardButtonColor, Text, OpenLink


# ============================================================
# INLINE-клавиатуры (прикреплены к сообщению)
# ============================================================

def quiz_start_kb() -> str:
    """Старт квиза."""
    kb = Keyboard(inline=True)
    kb.add(Text("Далее 👉", payload={"cmd": "quiz:start"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def quiz_false_kb() -> str:
    """Перезапуск квиза."""
    kb = Keyboard(inline=True)
    kb.add(Text("🔄 Перезапуск", payload={"cmd": "quiz:restore"}), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()


def activation_kb() -> str:
    """Активация бота: оплата или промокод."""
    kb = Keyboard(inline=True)
    kb.add(Text("💳 Оплатить", payload={"cmd": "pay_access"}), color=KeyboardButtonColor.POSITIVE)
    kb.row()
    kb.add(Text("🔑 Ввести код активации", payload={"cmd": "enter_promo"}))
    return kb.get_json()


def kb_activation() -> str:
    """Кнопка после ввода промокода."""
    kb = Keyboard(inline=True)
    kb.add(Text("Всё ясно, погнали! 🚀", payload={"cmd": "kb_activation"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def first_request_kb() -> str:
    """Первый запрос к AI."""
    kb = Keyboard(inline=True)
    kb.add(Text("Подобрать коляску 🎯", payload={"cmd": "first_request"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def rules_mode_kb() -> str:
    """Для branch == service_only."""
    kb = Keyboard(inline=True)
    kb.add(Text("💢 Как не сломать коляску", payload={"cmd": "rules_mode"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def next_service_kb() -> str:
    """Следующий шаг (после памятки)."""
    kb = Keyboard(inline=True)
    kb.add(Text("Следующий шаг ➡️", payload={"cmd": "next_service"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def get_wb_link_kb() -> str:
    """Ссылка на WB."""
    kb = Keyboard(inline=True)
    kb.add(Text("🟣 Смазка на WB", payload={"cmd": "get_wb_link"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def ai_mode_kb() -> str:
    """Выбор режима AI."""
    kb = Keyboard(inline=True)
    kb.add(Text("🎯 Подобрать коляску", payload={"cmd": "mode_catalog"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("❓ Другой запрос", payload={"cmd": "mode_info"}))
    return kb.get_json()


def ai_mode_with_balance_kb() -> str:
    """Выбор режима AI + кнопка пополнения."""
    kb = Keyboard(inline=True)
    kb.add(Text("🎯 Подобрать коляску", payload={"cmd": "mode_catalog"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("❓ Другой запрос", payload={"cmd": "mode_info"}))
    kb.row()
    kb.add(Text("➕ Пополнить баланс 💳", payload={"cmd": "top_up_balance"}), color=KeyboardButtonColor.POSITIVE)
    return kb.get_json()


def pay_kb() -> str:
    """Выбор тарифа оплаты."""
    kb = Keyboard(inline=True)
    kb.add(Text("1 запрос — 29₽", payload={"cmd": "pay29"}))
    kb.add(Text("50 запросов — 950₽", payload={"cmd": "pay950"}))
    kb.row()
    kb.add(Text("10 запросов — 190₽", payload={"cmd": "pay190"}))
    return kb.get_json()


def payment_button_kb(url: str) -> str:
    """Кнопка-ссылка на оплату."""
    kb = Keyboard(inline=True)
    kb.add(OpenLink(link=url, label="💳 Перейти к оплате"))
    return kb.get_json()


def magazine_map_kb(map_url: str | None) -> str | None:
    """Ссылка на карту магазина."""
    if not map_url:
        return None
    kb = Keyboard(inline=True)
    kb.add(OpenLink(link=map_url, label="🗺 Открыть на карте"))
    return kb.get_json()


# ============================================================
# ОСНОВНАЯ клавиатура (внизу чата, как Reply Keyboard)
# ============================================================

def main_menu_kb() -> str:
    """
    Главное меню — аналог команд Telegram.
    VK не поддерживает /команды, поэтому используем кнопки.
    """
    kb = Keyboard(one_time=False)
    kb.add(Text("🤖 AI-консультант", payload={"cmd": "ai_consultant"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("📖 Путеводитель", payload={"cmd": "guide"}))
    kb.add(Text("💢 Правила", payload={"cmd": "rules"}))
    kb.row()
    kb.add(Text("📍 Магазин", payload={"cmd": "magazine"}))
    kb.add(Text("📝 Блог", payload={"cmd": "blog"}))
    kb.row()
    kb.add(Text("❓ Помощь", payload={"cmd": "help"}))
    return kb.get_json()
