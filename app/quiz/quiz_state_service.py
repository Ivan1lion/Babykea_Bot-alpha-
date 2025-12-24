from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserQuizProfile, User
from app.quiz.config_quiz import QUIZ_CONFIG


#Получить или создать профиль квиза. Kвиз продолжался после рестарта, один профиль = одна строка
async def get_or_create_quiz_profile(
    session: AsyncSession,
    user: User
) -> UserQuizProfile:

    profile = await session.get(UserQuizProfile, user.id)

    if profile:
        return profile

    profile = UserQuizProfile(
        user_id=user.id,
        branch=None,
        current_level=1,
        data={}
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
    key = step["save_to"]
    value = step["options"][selected_option]["value"]

    profile.data[key] = value

    # если первый шаг — выбираем ветку
    if step.get("branch_by"):
        profile.branch = selected_option

    profile.current_level += 1

    session.add(profile)
    await session.commit()




# Назад (шаг –1)
async def go_back(
    session: AsyncSession,
    profile: UserQuizProfile,
):
    if profile.current_level == 1:
        return

    profile.current_level -= 1

    step = get_current_step(profile)
    key = step["save_to"]

    profile.data.pop(key, None)

    session.add(profile)
    await session.commit()




# Восстановление после рестарта
async def restore_quiz(
    session: AsyncSession,
    user: User
) -> UserQuizProfile:
    return await get_or_create_quiz_profile(session, user)

