from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


quiz_start = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Далее 👉",
                                                                         callback_data="quiz:start")]])

quiz_false = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Перезапуск",
                                                                         callback_data="quiz:start")]])

user_group = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="1 🤰", callback_data="pay30"),
     InlineKeyboardButton(text="2 👶", callback_data="pay550")],
     [InlineKeyboardButton(text="3", callback_data="pay2500")],
                                              ])


pay = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="1 запрос - 30р.", callback_data="pay30"),
     InlineKeyboardButton(text="20 запросов - 550р.", callback_data="pay550")],
     [InlineKeyboardButton(text="100 запросов - 2500р.", callback_data="pay2500")],
                                              ])

def payment_button_keyboard(confirmation_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=confirmation_url)]
    ])