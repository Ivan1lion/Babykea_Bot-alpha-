from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.crud import get_or_create_user
from app.quiz.renderer import render_quiz_step, resolve_media, build_keyboard
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
    bot: Bot,
    session: AsyncSession,
):
    await call.answer("Один момент")
    user = await get_or_create_user(
        session=session,
        telegram_id=call.from_user.id,
        username=call.from_user.username,
    )
    profile = await get_or_create_quiz_profile(session, user)

    # очищаем только временный выбор
    profile.data.pop("_selected", None)
    session.add(profile)
    await session.commit()

    # # Удаляем предыдущее сообщение с видео и кнопкой (если нужно)
    # try:
    #     await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    # except Exception as e:
    #     print(f"Не удалось удалить старое сообщение: {e}")

    # Убираем кнопки из старого видео
    try:
        await bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except Exception as e:
        print(f"Не удалось убрать кнопки с видео: {e}")

    # Первый шаг — отправляем фото-квиз заново
    step = get_current_step(profile)
    photo, text = resolve_media(step, None)
    msg = await bot.send_photo(
        chat_id=call.message.chat.id,
        photo=photo,
        caption=text,
        reply_markup=build_keyboard(step, profile, None)
    )

    # сохраняем message_id нового фото-сообщения для редактирования
    profile.quiz_message_id = msg.message_id
    session.add(profile)
    await session.commit()





# Выбор варианта (кнопка 1 / 2 / 3 и т.д.)
# callback вида: quiz:select:<option_key>
# 🔹 Зачем:
# пользователь может тыкать разные кнопки
# «Далее» станет активным
# ничего в БД «навсегда» не пишем
@quiz_router.callback_query(F.data.startswith("quiz:select:"))
async def quiz_select_option(
    call: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
):
    selected_option = call.data.split(":")[2]

    user = await get_or_create_user(
        session=session,
        telegram_id=call.from_user.id,
        username=call.from_user.username,
    )
    profile = await get_or_create_quiz_profile(session, user)

    # 🔹 ТОЛЬКО временный выбор
    profile.data["_selected"] = selected_option
    session.add(profile)
    await session.commit()

    await render_quiz_step(
        bot=bot,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        profile=profile,
        selected=selected_option,
    )





# Кнопка «Далее»
# 🔹 ВАЖНО:
# только тут данные навсегда пишутся в БД
# ветка определяется
# уровень увеличивается
@quiz_router.callback_query(F.data == "quiz:next")
async def quiz_next(
    call: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
):
    user = await get_or_create_user(
    session=session,
    telegram_id=call.from_user.id,
    username=call.from_user.username,
)
    profile = await get_or_create_quiz_profile(session, user)

    step = get_current_step(profile)
    selected_option = profile.data.get("_selected")

    # ⛔ запрет «Далее» без выбора
    if not validate_next(selected_option):
        await call.answer(
            "Выберите вариант и затем нажмите «Далее»",
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

    # 🏁 КВИЗ ЗАВЕРШЁН
    if profile.completed:
        await call.message.edit_caption(
            caption=(
                "✅ Спасибо! Квиз завершён.\n\n"
                "Я сохранил ваши ответы и скоро помогу "
                "подобрать подходящую коляску 👶🛒"
            ),
            reply_markup=None,
        )
        return

    # иначе — обычный переход
    await render_quiz_step(
        bot=bot,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        profile=profile,
        selected=None,
    )





# Кнопка «Назад»
# 🔹 Что делает:
# откатывает уровень
# удаляет сохранённое значение шага
# корректно работает в ветках
@quiz_router.callback_query(F.data == "quiz:back")
async def quiz_back(
    call: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
):
    await call.answer()
    user = await get_or_create_user(
        session=session,
        telegram_id=call.from_user.id,
        username=call.from_user.username,
    )
    profile = await get_or_create_quiz_profile(session, user)

    await go_back(session, profile)

    await render_quiz_step(
        bot=bot,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        profile=profile,
        selected=None,
    )

