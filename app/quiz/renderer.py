from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.quiz.config_quiz import QUIZ_CONFIG
from app.db.models import UserQuizProfile



# Сбор клавиатуры под шаг
def build_keyboard(
    step: dict,
    selected: str | None = None,
) -> InlineKeyboardMarkup:

    buttons = []

    for option_key, option in step["options"].items():
        text = option["text"]
        if selected == option_key:
            text = f"✅ {text}"

        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"quiz:select:{option_key}"
            )
        ])

    nav = []

    if step.get("has_back"):
        nav.append(
            InlineKeyboardButton(
                text="⬅ Назад",
                callback_data="quiz:back"
            )
        )

    nav.append(
        InlineKeyboardButton(
            text="➡ Далее",
            callback_data="quiz:next"
        )
    )

    buttons.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=buttons)




# Определяем фото и текст
def resolve_media(step: dict, selected: str | None):
    if selected and "preview" in step["options"][selected]:
        media = step["options"][selected]["preview"]
    else:
        media = step["default"]

    return media["photo"], media["text"]




# Рендер шага (редактирование)
async def render_quiz_step(
    bot: Bot,
    chat_id: int,
    message_id: int,
    profile: UserQuizProfile,
    selected: str | None = None,
):
    branch = profile.branch or "root"
    step = QUIZ_CONFIG[branch][profile.current_level]

    photo, text = resolve_media(step, selected)
    keyboard = build_keyboard(step, selected)

    await bot.edit_message_media(
        chat_id=chat_id,
        message_id=message_id,
        media={
            "type": "photo",
            "media": photo,
            "caption": text
        },
        reply_markup=keyboard
    )

