"""
VK-клавиатуры — полный набор, аналог Telegram keyboards.

VK типы клавиатур:
  - inline=True  → прикреплена к сообщению (как Telegram InlineKeyboard)
  - inline=False → внизу чата (как Telegram ReplyKeyboard)

VK кнопки:
  - Text(label, payload) → обычная кнопка с callback
  - OpenLink(link, label) → кнопка-ссылка
"""

import json
from vkbottle import Keyboard, KeyboardButtonColor, Text, OpenLink


# ============================================================
# INLINE — прикреплены к сообщению
# ============================================================

def quiz_start_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("Далее 👉", payload={"cmd": "quiz:start"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def quiz_false_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("🔄 Перезапуск", payload={"cmd": "quiz:restore"}), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()


def activation_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("💳 Оплатить", payload={"cmd": "pay_access"}), color=KeyboardButtonColor.POSITIVE)
    kb.row()
    kb.add(Text("🔑 Ввести код активации", payload={"cmd": "enter_promo"}))
    return kb.get_json()


def kb_activation() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("Всё ясно, погнали! 🚀", payload={"cmd": "kb_activation"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def first_request_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("Подобрать коляску 🎯", payload={"cmd": "first_request"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def rules_mode_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("💢 Как не сломать коляску", payload={"cmd": "rules_mode"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def next_service_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("Следующий шаг ➡️", payload={"cmd": "next_service"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def get_wb_link_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("🟣 Смазка на WB", payload={"cmd": "get_wb_link"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def ai_mode_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("🎯 Подобрать коляску", payload={"cmd": "mode_catalog"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("❓ Другой запрос", payload={"cmd": "mode_info"}))
    return kb.get_json()


def ai_mode_with_balance_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("🎯 Подобрать коляску", payload={"cmd": "mode_catalog"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("❓ Другой запрос", payload={"cmd": "mode_info"}))
    kb.row()
    kb.add(Text("➕ Пополнить баланс 💳", payload={"cmd": "top_up_balance"}), color=KeyboardButtonColor.POSITIVE)
    return kb.get_json()


def pay_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("1 запрос — 29₽", payload={"cmd": "pay29"}))
    kb.add(Text("50 запросов — 950₽", payload={"cmd": "pay950"}))
    kb.row()
    kb.add(Text("10 запросов — 190₽", payload={"cmd": "pay190"}))
    return kb.get_json()


def payment_button_kb(url: str) -> str:
    kb = Keyboard(inline=True)
    kb.add(OpenLink(link=url, label="💳 Перейти к оплате"))
    return kb.get_json()


def magazine_map_kb(map_url: str | None) -> str | None:
    if not map_url:
        return None
    kb = Keyboard(inline=True)
    kb.add(OpenLink(link=map_url, label="🗺 Открыть на карте"))
    return kb.get_json()


# ============================================================
# ПРОФИЛЬ — /config
# ============================================================

def config_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("🔑 Промокод", payload={"cmd": "promo"}))
    kb.add(Text("🛠 Плановое ТО", payload={"cmd": "service"}))
    kb.row()
    kb.add(Text("🔄 Квиз заново", payload={"cmd": "quiz_restart"}))
    kb.add(Text("📧 Email", payload={"cmd": "email"}))
    kb.row()
    kb.add(Text("📃 Оферта", payload={"cmd": "offer"}))
    return kb.get_json()


# ============================================================
# БЛОГ
# ============================================================

def blog_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("🔔 Вкл/Откл рассылку", payload={"cmd": "toggle_blog_sub"}))
    return kb.get_json()


# ============================================================
# ПОМОЩЬ
# ============================================================

def help_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("«Скрипит!»", payload={"cmd": "faq_1"}))
    kb.add(Text("«Снять колеса»", payload={"cmd": "faq_2"}))
    kb.row()
    kb.add(Text("«Голова ниже ног»", payload={"cmd": "faq_3"}))
    kb.add(Text("«Атмосферы»", payload={"cmd": "faq_4"}))
    kb.row()
    kb.add(Text("🤖 Спросить AI", payload={"cmd": "ai_info"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("✍️ Написать мастеру", payload={"cmd": "contact_master"}))
    return kb.get_json()


# ============================================================
# МАСТЕР (обратная связь)
# ============================================================

def master_start_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Text("💬 Поделиться историей", payload={"cmd": "mf_start"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


# ============================================================
# КВИЗ — динамическая клавиатура
# ============================================================

def build_quiz_keyboard(step: dict, profile, selected: str | None = None) -> str:
    """
    Строит VK inline-клавиатуру для шага квиза.
    Аналог renderer.build_keyboard() из Telegram.
    """
    kb = Keyboard(inline=True)

    for option_key, option in step["options"].items():
        text = option["button"]
        if selected == option_key:
            text = f"✅ {text}"

        kb.add(Text(text, payload={"cmd": f"quiz:select:{option_key}"}))
        kb.row()

    # Навигация
    nav_row = []
    if profile.current_level > 1:
        kb.add(Text("⬅ Назад", payload={"cmd": "quiz:back"}))

    kb.add(Text("Далее ➡", payload={"cmd": "quiz:next"}), color=KeyboardButtonColor.PRIMARY)

    return kb.get_json()


# ============================================================
# ГЛАВНОЕ МЕНЮ (reply keyboard — внизу чата)
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
    kb.add(Text("✅ Памятка", payload={"cmd": "manual"}))
    kb.add(Text("📍 Магазин", payload={"cmd": "contacts"}))
    kb.row()
    kb.add(Text("📝 Блог", payload={"cmd": "blog"}))
    kb.add(Text("👤 Профиль", payload={"cmd": "config"}))
    kb.row()
    kb.add(Text("❓ Помощь", payload={"cmd": "help"}))
    return kb.get_json()
