import os

from aiogram import Router, Bot, F
from aiogram.types import Message, BotCommand, LinkPreviewOptions, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import closed_menu
from app.db.models import User


standard_router = Router()


bot_menu = [
    BotCommand(command="guide", description="⁉️ Как подобрать коляску"),
    BotCommand(command="rules", description="💢 Как не сломать коляску"),
    BotCommand(command="manual", description="✅ Как продлить жизнь коляске"),
    BotCommand(command="ai_consultant", description="🤖 AI-консультант"),
    BotCommand(command="blog", description="️🧔‍♂️ Блог мастера"),
    BotCommand(command="help", description="🆘 Помощь"),
    BotCommand(command="config", description="👤 Мой профиль"),
    BotCommand(command="contacts", description="📍 Магазин колясок"),
    BotCommand(command="offer", description="📃 Пользовательское соглашение"),
]


my_channel_id = int(os.getenv("MY_CHANNEL_ID"))


# Генератор кнопок для управления подписки на рассылку из моего канала
def get_blog_kb(is_subscribed: bool) -> InlineKeyboardMarkup:
    if is_subscribed:
        btn_text = "Откл. сообщения из блога"
        color = "danger"
    else:
        btn_text = "Вкл. сообщения из блога"
        color = "success"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text,
                              callback_data="toggle_blog_sub",
                              style=color)]
    ])


@standard_router.message(Command("blog"))
async def blog_cmd(message: Message, session: AsyncSession):
    if await closed_menu(message=message, session=session):
        return

    # 1. Проверяем статус подписки
    stmt = select(User.subscribed_to_author).where(User.telegram_id == message.from_user.id)
    is_subscribed = (await session.execute(stmt)).scalar_one_or_none()

    if is_subscribed is None:
        is_subscribed = True

    # 2. Формируем клавиатуру
    kb = get_blog_kb(is_subscribed)

    # 3. Текст сообщения
    blog_text = (
        "Мой канал <a href='https://t.me/Ivan_PROkolyaski/8'>Иван [PROkolyaski]</a>\n\n"
        "0. <a href='https://telegra.ph/Obo-mne-01-14-9'>Обо мне</a>\n\n"
        "<a href='https://t.me/Ivan_PROkolyaski'>#мысливслух</a>\n"
        "<blockquote>не рекомендации, но информация к размышлению молодым родителям</blockquote>\n\n"
        "1. Почему при выборе коляски нельзя доверять отзывам в интернете\n\n"
        "2. Про современные вездеходы с маленькими передними колёсами (Джулз)\n\n"
        "3. Сколько должно быть колясок у ребенка? Две или все-таки одной достаточно?\n\n"
        "4. Почему покупать коляску из расчета что в случае чего её можно будет починить в корне неверно\n\n"
        "5. Про гарантийные обязательства продавцов колясок (Магазины могут лишь брать на себя обязательства ради лояльности клиента)\n\n\n"
        "<a href='https://t.me/Ivan_PROkolyaski'>#маркетинговыеТефтели</a>\n"
        "<blockquote>мое мнение о маркетинговых уловках и манипуляциях со стороны производителей детских колясок</blockquote>\n\n"
        "1. Коляски 3 в 1 - так ли необходима автолюлька\n\n"
        "2. Амортизация, системы антишок и прочая ерунда\n\n"
        "3. Чем коляска за 150.000₽ отличается от коляски за 60.000₽?\n\n"
    )

    # 4. Отправляем
    await message.answer_photo(
        photo="AgACAgIAAyEGAATQjmD4AANuaZnp85G2dqnEAAEE7tjDMTHOaparAALHGWsbAbrRSEMyKwp3hwQVAQADAgADdwADOgQ"
    )
    await message.answer(
        text=blog_text,
        reply_markup=kb,
        disable_web_page_preview=False
    )




@standard_router.callback_query(F.data == "toggle_blog_sub")
async def process_toggle_blog_sub(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id

    # 1. Получаем текущий статус
    stmt = select(User.subscribed_to_author).where(User.telegram_id == user_id)
    is_subscribed = (await session.execute(stmt)).scalar_one_or_none()

    if is_subscribed is None:
        is_subscribed = True

    # 2. Инвертируем статус (меняем True на False и наоборот)
    new_status = not is_subscribed

    # 3. Обновляем БД
    update_stmt = (
        update(User)
        .where(User.telegram_id == user_id)
        .values(subscribed_to_author=new_status)
    )
    await session.execute(update_stmt)
    await session.commit()

    # 4. Меняем кнопку на сообщении
    kb = get_blog_kb(new_status)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass # Игнорируем ошибку при спаме кликами

    # 5. Показываем всплывающее уведомление
    if new_status:
        # Юзер включил рассылку
        await callback.answer("✅ Готово!"
                              "\n\nНовые посты из канала будут дублироваться сюда, чтобы вы ничего не пропустили",
                              show_alert=True)
    else:
        # Юзер отключил рассылку
        await callback.answer("🔕 Блог мастера отключен"
                              "\n\nВсе важные технические напоминания (вроде планового ТО) при этом сохранятся!",
                              show_alert=True)




@standard_router.message(Command("offer"))
async def offer_cmd(message: Message):
    text_offer = (f"1. <a href='https://telegra.ph/Oferta-dlya-chat-bota-Babykea-Bot-Babykea-07-14'>Публичная оферта, "
                  f"Пользовательское соглашение, условия эксплуатации и обслуживания</a>\n\n"
                  f"2. <a href='https://telegra.ph/Politika-konfidencialnosti-07-26-9'>Политика Конфиденциальности</a>")
    await message.answer(text=text_offer, link_preview_options=LinkPreviewOptions(is_disabled=True))