from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from app.core.quiz.config_quiz import QUIZ_CONFIG
from app.core.db.models import UserQuizProfile
import app.platforms.telegram.keyboards as kb



# Сбор клавиатуры под шаг
def build_keyboard(
    step: dict,
    profile,
    selected: str | None = None,
) -> InlineKeyboardMarkup:

    buttons = []

    for option_key, option in step["options"].items():
        text = option["button"]
        if selected == option_key:
            text = f"✅ {text}"

        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"quiz:select:{option_key}"
            )
        ])

    nav = []

    # ⬅ Назад — если уровень больше 1
    if profile.current_level > 1:
        nav.append(
            InlineKeyboardButton(
                text="⬅ Назад",
                callback_data="quiz:back"
            )
        )

    nav.append(
        InlineKeyboardButton(
            text="Далее ➡",
            callback_data="quiz:next"
        )
    )

    buttons.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=buttons)





# Определяем фото и текст
def resolve_media(step: dict, selected: str | None):
    # если выбран вариант и у него есть preview — показываем его
    if selected:
        option = step["options"].get(selected)
        if option and "preview" in option:
            return option["preview"]["photo"], option["preview"]["text"]

    # иначе — базовое фото и текст шага
    return step["photo"], step["text"]





# Рендер шага (редактирование)
async def render_quiz_step(
    bot: Bot,
    chat_id: int,
    message_id: int,
    profile: UserQuizProfile,
    selected: str | None = None,
):
    try:
        branch = profile.branch or "root"
        step = QUIZ_CONFIG[branch][profile.current_level]

        photo, text = resolve_media(step, selected)
        keyboard = build_keyboard(step, profile, selected)

        await bot.edit_message_media(
            chat_id=chat_id,
            message_id=message_id,
            media={
                "type": "photo",
                "media": photo,
                "caption": text,
            },
            reply_markup=keyboard,
        )

    except TelegramBadRequest:
        # ❌ сообщение не найдено / нельзя отредактировать
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "❌ Произошла ошибка.\n\n"
                "Попробуйте ещё раз — нажмите кнопку ниже 👇"
            ),
            reply_markup=kb.quiz_false,
        )

