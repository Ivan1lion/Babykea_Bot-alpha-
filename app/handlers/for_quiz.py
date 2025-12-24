from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.quiz.renderer import render_quiz_step
from app.quiz.config_quiz import QUIZ_CONFIG
from app.quiz.quiz_state_service import (
    get_or_create_quiz_profile,
    get_current_step,
    validate_next,
    save_and_next,
    go_back,
)


quiz_router = Router()

#Старт квиза (после нажатия кнопки запуска квиза)
# 🔹 Что происходит:
# получаем пользователя
# cоздаём / восстанавливаем профиль квиза
# рендерим текущий шаг (или первый)
@quiz_router.callback_query(F.data == "quiz:start")
async def quiz_start(
    call: CallbackQuery,
    session: AsyncSession,
):
    user = await session.get(User, call.from_user.id)
    profile = await get_or_create_quiz_profile(session, user)

    step = get_current_step(profile)

    await render_quiz_step(call, profile, step)




# Выбор варианта (кнопка 1 / 2 / 3 и т.д.)
# callback вида: quiz:select:<option_key>
# 🔹 Зачем:
# пользователь может тыкать разные кнопки
# «Далее» станет активным
# ничего в БД «навсегда» не пишем
@quiz_router.callback_query(F.data.startswith("quiz:select:"))
async def quiz_select_option(
    call: CallbackQuery,
    session: AsyncSession,
):
    selected_option = call.data.split(":")[2]

    user = await session.get(User, call.from_user.id)
    profile = await get_or_create_quiz_profile(session, user)

    step = get_current_step(profile)

    # сохраняем выбранную кнопку ВРЕМЕННО (в data, без перехода)
    profile.data["_selected"] = selected_option

    session.add(profile)
    await session.commit()

    await render_quiz_step(call, profile, step)




# Кнопка «Далее»
# 🔹 ВАЖНО:
# только тут данные навсегда пишутся в БД
# ветка определяется
# уровень увеличивается
@quiz_router.callback_query(F.data == "quiz:next")
async def quiz_next(
    call: CallbackQuery,
    session: AsyncSession,
):
    user = await session.get(User, call.from_user.id)
    profile = await get_or_create_quiz_profile(session, user)

    step = get_current_step(profile)

    selected_option = profile.data.get("_selected")

    # ⛔ запрет «Далее» без выбора
    if not validate_next(selected_option):
        await call.answer(
            "Выберите вариант, затем нажмите «Далее»",
            show_alert=True,
        )
        return

    await save_and_next(
        session=session,
        profile=profile,
        step=step,
        selected_option=selected_option,
    )

    # очищаем временный выбор
    profile.data.pop("_selected", None)
    session.add(profile)
    await session.commit()

    next_step = get_current_step(profile)
    await render_quiz_step(call, profile, next_step)




# Кнопка «Назад»
# 🔹 Что делает:
# откатывает уровень
# удаляет сохранённое значение шага
# корректно работает в ветках
@quiz_router.callback_query(F.data == "quiz:back")
async def quiz_back(
    call: CallbackQuery,
    session: AsyncSession,
):
    user = await session.get(User, call.from_user.id)
    profile = await get_or_create_quiz_profile(session, user)

    await go_back(session, profile)

    step = get_current_step(profile)
    await render_quiz_step(call, profile, step)

