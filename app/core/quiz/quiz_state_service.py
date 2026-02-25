from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db.models import UserQuizProfile, User
from app.core.quiz.config_quiz import QUIZ_CONFIG


#Получить или создать профиль квиза. Kвиз продолжался после рестарта, один профиль = одна строка
async def get_or_create_quiz_profile(
    session: AsyncSession,
    user: User
) -> UserQuizProfile:
    result = await session.execute(
        select(UserQuizProfile).where(UserQuizProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()

    if profile:
        return profile

    profile = UserQuizProfile(
        user_id=user.id,
        branch=None,
        current_level=1,
        data={},
        completed=False,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    return profile




#Получить текущий шаг из конфига
def get_current_step(profile: UserQuizProfile) -> dict:
    branch = profile.branch or "root"
    level = profile.current_level

    try:
        return QUIZ_CONFIG[branch][level]
    except KeyError:
        raise ValueError("Некорректный шаг квиза")



# Проверка окончания квиза
def is_last_step(profile: UserQuizProfile) -> bool:
    branch = profile.branch or "root"
    steps = QUIZ_CONFIG.get(branch, {})
    return profile.current_level not in steps




#Проверка: можно ли нажать «Далее»
def validate_next(selected_option: str | None) -> bool:
    return selected_option is not None




#Сохранить ответ и перейти дальше
# - атомарная запись
# - всё лежит в одном JSON
# - легко читать AI
async def save_and_next(
    session: AsyncSession,
    profile: UserQuizProfile,
    step: dict,
    selected_option: str,
):
    option = step["options"].get(selected_option)
    if not option:
        return

    # 🔹 сохраняем реальные ответы
    save_data = option.get("save", {})
    profile.data.update(save_data)

    # 🏁 ЗАВЕРШЕНИЕ КВИЗА ПО КНОПКЕ
    if option.get("finish"):
        profile.completed = True
        profile.data.pop("_selected", None)
        session.add(profile)
        await session.commit()
        return

    # 🔹 переход по ветке
    if "branch" in option:
        profile.branch = option["branch"]
        profile.current_level = 2
    else:
        next_level = step.get("next_level")

        if next_level is None:
            # 🏁 КОНЕЦ КВИЗА
            profile.completed = True
        else:
            profile.current_level = next_level

    # 🔹 очистка временного выбора
    profile.data.pop("_selected", None)

    session.add(profile)
    await session.commit()




# Назад (шаг –1)
async def go_back(session: AsyncSession, profile: UserQuizProfile):
    if profile.current_level == 1 and profile.branch is None:
        # Уже на самом первом шаге root — дальше не откатываем
        return

    profile.current_level -= 1

    branch = profile.branch or "root"

    # Если уровня нет в ветке, возвращаемся в root
    if profile.current_level not in QUIZ_CONFIG.get(branch, {}):
        profile.branch = None
        profile.current_level = 1
        step = QUIZ_CONFIG["root"][1]
    else:
        step = QUIZ_CONFIG[branch][profile.current_level]

    # Удаляем сохранённое значение текущего шага (если есть)
    key = step.get("save_to")
    if key:
        profile.data.pop(key, None)

    session.add(profile)
    await session.commit()





# Восстановление после рестарта
async def restore_quiz(
    session: AsyncSession,
    user: User
) -> UserQuizProfile:
    return await get_or_create_quiz_profile(session, user)

