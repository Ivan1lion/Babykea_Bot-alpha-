"""
VK-клавиатуры — полный набор, аналог Telegram keyboards.

ВАЖНО: Все inline-кнопки используют тип Callback (не Text!).
  - Text кнопки дублируют текст в чат (как отправленное сообщение)
  - Callback кнопки работают "тихо" — генерируют message_event

VK типы клавиатур:
  - inline=True  → прикреплена к сообщению (Callback-кнопки)
  - inline=False → внизу чата (Text-кнопки для главного меню)
"""

import json
from vkbottle import Keyboard, KeyboardButtonColor, Text, Callback, OpenLink


# ============================================================
# INLINE — прикреплены к сообщению (Callback — "тихие")
# ============================================================

def quiz_start_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("Далее 👉", payload={"cmd": "quiz:start"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def quiz_false_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("🔄 Перезапуск", payload={"cmd": "quiz:restore"}), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()


def activation_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("💳 Оплатить", payload={"cmd": "pay_access"}), color=KeyboardButtonColor.POSITIVE)
    kb.row()
    kb.add(Callback("🔑 Ввести код активации", payload={"cmd": "enter_promo"}))
    return kb.get_json()


def kb_activation() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("Всё ясно, погнали! 🚀", payload={"cmd": "kb_activation"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def first_request_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("Подобрать коляску 🎯", payload={"cmd": "first_request"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def rules_mode_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("💢 Как не сломать коляску", payload={"cmd": "rules_mode"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def next_service_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("Следующий шаг ➡️", payload={"cmd": "next_service"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def get_wb_link_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("🟣 Смазка на WB", payload={"cmd": "get_wb_link"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


def ai_mode_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("🎯 Подобрать коляску", payload={"cmd": "mode_catalog"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Callback("❓ Другой запрос", payload={"cmd": "mode_info"}))
    return kb.get_json()


def ai_mode_with_balance_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("🎯 Подобрать коляску", payload={"cmd": "mode_catalog"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Callback("❓ Другой запрос", payload={"cmd": "mode_info"}))
    kb.row()
    kb.add(Callback("➕ Пополнить баланс 💳", payload={"cmd": "top_up_balance"}), color=KeyboardButtonColor.POSITIVE)
    return kb.get_json()


def pay_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("1 запрос — 29₽", payload={"cmd": "pay29"}))
    kb.add(Callback("50 запросов — 950₽", payload={"cmd": "pay950"}))
    kb.row()
    kb.add(Callback("10 запросов — 190₽", payload={"cmd": "pay190"}))
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
    kb.add(Callback("🔑 Промокод", payload={"cmd": "promo"}))
    kb.add(Callback("🛠 Плановое ТО", payload={"cmd": "service"}))
    kb.row()
    kb.add(Callback("🔄 Квиз заново", payload={"cmd": "quiz_restart"}))
    kb.add(Callback("📧 Email", payload={"cmd": "email"}))
    kb.row()
    kb.add(Callback("📃 Оферта", payload={"cmd": "offer"}))
    return kb.get_json()


# ============================================================
# БЛОГ
# ============================================================

def blog_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("🔔 Вкл/Откл рассылку", payload={"cmd": "toggle_blog_sub"}))
    return kb.get_json()


# ============================================================
# ПОМОЩЬ
# ============================================================

def help_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("«Скрипит!»", payload={"cmd": "faq_1"}))
    kb.add(Callback("«Снять колеса»", payload={"cmd": "faq_2"}))
    kb.row()
    kb.add(Callback("«Голова ниже ног»", payload={"cmd": "faq_3"}))
    kb.add(Callback("«Атмосферы»", payload={"cmd": "faq_4"}))
    kb.row()
    kb.add(Callback("🤖 Спросить AI", payload={"cmd": "ai_info"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Callback("✍️ Написать мастеру", payload={"cmd": "contact_master"}))
    return kb.get_json()


# ============================================================
# МАСТЕР (обратная связь)
# ============================================================

def master_start_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("💬 Поделиться историей", payload={"cmd": "mf_start"}), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


# ============================================================
# КВИЗ — динамическая клавиатура (Callback)
# ============================================================

def build_quiz_keyboard(step: dict, profile, selected: str | None = None) -> str:
    """
    Строит VK inline-клавиатуру (Callback) для шага квиза.
    Аналог renderer.build_keyboard() из Telegram.
    """
    kb = Keyboard(inline=True)

    for option_key, option in step["options"].items():
        text = option["button"]
        if selected == option_key:
            text = f"✅ {text}"

        kb.add(Callback(text, payload={"cmd": f"quiz:select:{option_key}"}))
        kb.row()

    # Навигация — "Назад" и "Далее" на одной строке
    if profile.current_level > 1:
        kb.add(Callback("⬅ Назад", payload={"cmd": "quiz:back"}))

    kb.add(Callback("Далее ➡", payload={"cmd": "quiz:next"}), color=KeyboardButtonColor.PRIMARY)

    return kb.get_json()


# ============================================================
# ГЛАВНОЕ МЕНЮ (reply keyboard — внизу чата)
# Здесь ОСТАЁТСЯ Text — это НЕ inline, а кнопки внизу экрана.
# Они должны быть Text, т.к. VK не поддерживает Callback
# для обычных (не inline) клавиатур.
# ============================================================

def main_menu_kb() -> str:
    """
    Главное меню — аналог команд Telegram.
    VK не поддерживает /команды, поэтому используем Text-кнопки.
    """
    kb = Keyboard(one_time=False)
    kb.add(Text("⁉️ Как подобрать коляску", payload={"cmd": "guide"}))
    kb.row()
    kb.add(Text("💢 Как не сломать коляску", payload={"cmd": "rules"}))
    kb.row()
    kb.add(Text("✅ Как продлить жизнь коляске", payload={"cmd": "manual"}))
    kb.row()
    kb.add(Text("🤖 AI-консультант", payload={"cmd": "ai_consultant"}))
    kb.row()
    kb.add(Text("🧔‍♂️ Блог мастера", payload={"cmd": "blog"}))
    kb.row()
    kb.add(Text("🆘 Помощь", payload={"cmd": "help"}))
    kb.row()
    kb.add(Text("👤 Мой профиль", payload={"cmd": "config"}))
    kb.row()
    kb.add(Text("📍 Магазин колясок", payload={"cmd": "contacts"}))
    kb.row()
    kb.add(Text("📃 Пользовательское соглашение", payload={"cmd": "offer"}))
    kb.row()
    return kb.get_json()



def guide_kb() -> str:
    kb = Keyboard(inline=True)
    kb.add(Callback("🤖 Начать умный подбор", payload={"cmd": "ai_consultant"}), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Callback("🔄 Перепройти квиз", payload={"cmd": "quiz_restart"}))
    return kb.get_json()