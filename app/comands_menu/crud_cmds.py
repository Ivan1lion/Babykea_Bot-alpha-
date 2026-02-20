import re
import urllib.parse
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Magazine
import app.handlers.keyboards as kb
from app.comands_menu.states import MenuStates
from app.comands_menu.email_for_menu import update_user_email
from app.db.crud import closed_menu


# Простая регулярка для email
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

crud_router = Router()


###########################################################################################################
@crud_router.message(Command("config"))
async def config_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    await message.answer(f"1. /quiz_restart - пройти квиз-опрос заново"
                         f"<blockquote>На основании ваших ответов AI-консультант подбирает и сравнивает коляски, "
                         f"соответствующие запросу</blockquote>"
                         f"\n\n2. /email - указать email для получения чеков"
                         f"<blockquote>При необходимости вы можете указать свой email для получения чеков  об оплате "
                         f"на свою почту</blockquote>"
                         f"\n\n3. /promo - Поделиться кодом активации с подругой"
                         )




# --- 1. Команда /email ---
@crud_router.message(Command("email"))
async def cmd_email_start(message: Message, state: FSMContext, session: AsyncSession):

    await message.answer(
        "📧 <b>Укажите ваш Email</b> для получения чеков.\n\n"
        "Отправьте адрес электронной почты в ответном сообщении 👇\n"
        "<i>(Или введите /cancel для отмены)</i>"
    )
    await state.set_state(MenuStates.waiting_for_email)


# --- 2. Ловим ввод Email (валидация и сохранение) ---
@crud_router.message(StateFilter(MenuStates.waiting_for_email))
async def process_email_input(message: Message, state: FSMContext, session: AsyncSession):
    email = message.text.strip().lower()

    # Если пользователь передумал
    if email.lower() == '/cancel':
        await message.answer("Ввод email отменен")
        await state.clear()
        return

    # Проверка формата (Валидация)
    if not re.match(EMAIL_REGEX, email):
        await message.answer(
            "❌ <b>Некорректный формат email</b>\n\n"
            "Пожалуйста, проверьте адрес и попробуйте снова.\n"
            "Пример: <code>example@mail.ru</code>"
        )
        return  # Не сбрасываем состояние, ждем повторного ввода

    # Сохранение в БД
    try:
        await update_user_email(session, message.from_user.id, email)
        await message.answer(f"✅ <b>Email сохранен!</b>"
                             f"\n\nЧеки будут приходить на: <code>{email}</code>"
                             )
        await state.clear()
    except Exception as e:
        await message.answer("Ошибка при сохранении. Попробуйте позже.")
        print(f"Error saving email: {e}")
        await state.clear()


@crud_router.message(Command("promo"))
async def promo_cmd(message: Message, session: AsyncSession):
    # 1. Достаем промокод юзера из БД
    stmt = select(User.promo_code).where(User.telegram_id == message.from_user.id)
    result = await session.execute(stmt)
    promo_code = result.scalar_one_or_none()

    # Защита от ошибки: если у юзера почему-то пустой промокод
    if not promo_code:
        await message.answer("У вас пока нет активного кода активации.")
        return

    # Настройки
    bot_link = "https://t.me/babykea_bot"
    photo_id = "AgACAgIAAyEGAATQjmD4AANnaY3ziPd3A8eUTwbZqo6-aqCuxmYAAmQaaxs1a3FI56_9NYQIxA0BAAMCAAN5AAM6BA"

    # 2. Формируем текст для ДРУГА (то, что появится в поле ввода при пересылке)
    share_text = f"Промокод на бесплатное подключение: {promo_code}"

    # Обязательно кодируем текст для URL (чтобы кириллица и пробелы не сломали ссылку)
    encoded_text = urllib.parse.quote(share_text)

    # Специальная ссылка Telegram для шаринга
    share_url = f"https://t.me/share/url?url={bot_link}&text={encoded_text}"

    # 3. Создаем кнопку с url-переходом
    share_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↗️ Поделиться ссылкой", url=share_url)]
    ])

    # 4. Формируем текст сообщения ВНУТРИ бота (для самого юзера)
    caption = (
        f"Ваш код активации <b>{promo_code}</b>\n\n"
        f"Вы можете им поделиться со своими друзьями:\n"
        f"{bot_link}"
    )

    # 5. Отправляем фото с текстом и кнопкой
    await message.answer_photo(
        photo=photo_id,
        caption=caption,
        reply_markup=share_kb
    )




#########################################################################################################


@crud_router.message(Command("contacts"))
async def contacts_cmd(message: Message, session: AsyncSession):

    if await closed_menu(message=message, session=session):
        return

    result = await session.execute(
        select(Magazine)
        .join(User, User.magazine_id == Magazine.id)
        .where(User.telegram_id == message.from_user.id)
    )
    magazine = result.scalar_one_or_none()

    if not magazine:
        await message.answer("Магазин не найден")
        return

    # 🔹 Спец-логика для Babykea
    if not magazine.name or magazine.name == "[Babykea]":
        await message.answer_photo(
            photo="https://i.postimg.cc/zBSgzjss/i.jpg",
            caption=(
                "🏆 <b>Магазины с высокой репутацией</b>\n\n"
                "• Первая-Коляска\u200B.РФ\n"
                "• Boan Baby\n"
                "• Lapsi\n"
                "• Кенгуру\n"
                "• Piccolo\n"
            ),
        )
        return

    # 🔹 Обычные магазины
    text_parts = [
        f"<blockquote>{magazine.name}</blockquote>\n",
        f"📍 Город: {magazine.city}",
        f"🏠 Адрес: {magazine.address}",
        f"🌐 Сайт: <a href='{magazine.url_website}'>{magazine.name_website}</a>",
    ]

    if magazine.username_magazine:
        text_parts.append(f"💬 Telegram: {magazine.username_magazine}")

    text = "\n".join(text_parts)

    if magazine.photo:
        await message.answer_photo(
            photo=magazine.photo,
            caption=text,
            reply_markup=kb.magazine_map_kb(magazine.map_url),
        )
    else:
        await message.answer(
            text,
            reply_markup=kb.magazine_map_kb(magazine.map_url),
        )
