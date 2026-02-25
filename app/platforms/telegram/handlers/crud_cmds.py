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

    await message.answer(f"1. /promo - поделиться кодом активации с подругой 🫶🏻"
                         f"\n\n2. /service - встать на плановое ТО"
                         f"\n\n3. /quiz_restart - пройти квиз-опрос заново"
                         f"<blockquote>На основании ваших ответов AI-консультант подбирает и сравнивает коляски, "
                         f"соответствующие запросу</blockquote>"
                         f"\n\n4. /email - указать email для получения чеков"
                         f"<blockquote>При необходимости вы можете указать свой email для получения чеков  об оплате "
                         f"на свою почту</blockquote>"
                         f"\n\n〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
                         "📌 <b>Памятка: 3 способа как не убить коляску</b>"
                         "\n\n🚿 <b>Никакого душа</b>"
                         "<blockquote>Не мойте колеса из шланга или в ванной. Вода вымоет смазку и подшипники сгниют "
                         "за месяц. Только влажная тряпка</blockquote>"
                         "\n\n🏋️ <b>Осторожнее с ручкой</b>"
                         "<blockquote>Не давите на неё всем весом перед бордюром — всегда помогайте ногой, "
                         "наступая на заднюю ось. Иначе разболтаете механизм складывания (а это самый дорогой ремонт)</blockquote>"
                         "\n\n🛢 <b>Забудьте про WD-40</b>"
                         "<blockquote>Вэдэшка 'сушит' подшипники, а любые бытовые масла работают как магнит для песка — через неделю "
                         "механизмы захрустят еще сильнее. Металл и пластик колясок смазывают только силиконом</blockquote>"
                         "\n\nСмазку, которой я пользуюсь в мастерской, обычно покупаю у своего поставщика запчастей и прочих "
                         "расходников. На валдберриз такую же не нашел, но нашел с такими же характеристиками, соотношение газа к "
                         "масляному раствору отличное и по цене норм"
                         # "\n\n<a href='https://www.wildberries.ru/catalog/191623733/detail.aspx?targetUrl=MI'>Смазка силиконовая "
                         # "для колясок https://www.wildberries.ru/catalog/191623733/detail.aspx?targetUrl=MI</a>"
                         "\n\nЕсли смазывать только коляску, то флакона хватит на пару лет",
                         reply_markup=kb.get_wb_link
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
    # Достаем промокод магазина И флаг активности
    stmt = (
        select(Magazine.promo_code, Magazine.is_promo_active)
        .select_from(User)
        .join(Magazine)  # INNER JOIN
        .where(User.telegram_id == message.from_user.id)
    )

    result = await session.execute(stmt)
    row = result.one_or_none()

    # Юзера уже в базе, но еще активировал промо и не связался с магазином (страховка)
    if not row:
        await message.answer("Нет-нет! Сначала закончите настройку и активируйте доступ к боту")
        return

    mag_promo, is_promo_active = row

    # Промокод деактивирован
    if not is_promo_active:
        await message.answer("Увы, срок действия Вашего промокода истек - им нельзя поделиться")
        return

    # Настройки
    bot_link = "https://t.me/babykea_bot"
    photo_id = "AgACAgIAAyEGAATQjmD4AANnaY3ziPd3A8eUTwbZqo6-aqCuxmYAAmQaaxs1a3FI56_9NYQIxA0BAAMCAAN5AAM6BA"

    # VIP-клиент
    if mag_promo == "[BABYKEA_PREMIUM]":
        share_promo = "BKEA-4K7X"
        caption = (
            f"👑 <b>У вас PREMIUM-доступ!</b>\n\n"
            f"Ваш аккаунт включает 50 запросов к AI-консультанту и глобальный поиск колясок по базам "
            f"магазинов с высокой репутацией. Ваш личный доступ привязан к аккаунту и не может быть передан\n\n"
            f"Но вы можете сделать подарок подруге! Отправьте ей гостевой промокод: <b>{share_promo}</b>\n\n"
            f"Он даст ей базовый бесплатный доступ к полезным материалам, уходу за коляской и "
            f"стандартному функционалу бота\n\n"
            f"{bot_link}"
        )

    # Обычный пользователь
    else:
        share_promo = mag_promo
        caption = (
            f"Ваш код активации: <b>{share_promo}</b>\n\n"
            f"Вы можете им поделиться со своими друзьями\n\n"
            f"{bot_link}"
        )

    # Формируем текст для друга
    share_text = (
        f"\nИщете коляску?\n"
        f"Подберем надежную модель под ваши условия\n\n"
        f"Уже купили?\n"
        f"Узнайте, как случайно не сломать её (80% поломок — вина владельцев!)\n\n"
        f"🔑 Ваш код для бесплатного доступа:\n\n"
        f"{share_promo}\n\n"
        f"(скопируйте его)"
    )

    encoded_text = urllib.parse.quote(share_text)
    share_url = f"https://t.me/share/url?url={bot_link}&text={encoded_text}"

    share_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↗️ Поделиться ссылкой", url=share_url)]
    ])

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
    if magazine.name == "[Babykea]":
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
