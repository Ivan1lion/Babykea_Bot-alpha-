from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


quiz_start = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Далее 👉",
                                                                         callback_data="quiz:start")]])



#Перезапуск квиз-формы в случае ошибки
quiz_false = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Перезапуск",
                                                                         callback_data="quiz:start")]])



#Переход к авторизации пользователя
kb_activation = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔓 Получить доступ",
                                                                         callback_data="kb_activation")]])



#Отправка 1го автоматического запроса к AI
first_request = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Подобрать коляску 🎯",
                                                                         callback_data="first_request")]])



#Для выбора типа использования AI
def get_ai_mode_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎯 Подобрать коляску", callback_data="mode_catalog")
    kb.button(text="❓ Другой запрос", callback_data="mode_info")
    kb.adjust(1) # Кнопки одна под другой
    return kb.as_markup()




activation_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Оплатить", callback_data="pay_access"),
        ],
        [
            InlineKeyboardButton(text="🔑 Ввести код активации", callback_data="enter_promo"),
        ],
    ]
)


#Ссылка на карту для раздела "📍 Магазин колясок"
def magazine_map_kb(map_url: str | None) -> InlineKeyboardMarkup | None:
    if not map_url:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗺 Открыть на карте",
                    url=map_url,
                )
            ]
        ]
    )


#Оплата запросов к AI ассистенту
pay = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="1 запрос - 29р.", callback_data="pay29"),
     InlineKeyboardButton(text="50 запросов - 950р.", callback_data="pay950")],
     [InlineKeyboardButton(text="10 запросов - 190р.", callback_data="pay190")],
                                              ])

def payment_button_keyboard(confirmation_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=confirmation_url)]
    ])


