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
    # 1. Достаем ТОЛЬКО промокод магазина, к которому привязан юзер
    stmt = (
        select(Magazine.promo_code)
        .select_from(User)
        .outerjoin(Magazine)  # Безопасное присоединение через ForeignKey
        .where(User.telegram_id == message.from_user.id)
    )

    result = await session.execute(stmt)
    # Получаем либо текст промокода магазина, либо None (если магазина нет)
    mag_promo = result.scalar_one_or_none()

    # Настройки
    bot_link = "https://t.me/babykea_bot"
    photo_id = "AgACAgIAAyEGAATQjmD4AANnaY3ziPd3A8eUTwbZqo6-aqCuxmYAAmQaaxs1a3FI56_9NYQIxA0BAAMCAAN5AAM6BA"

    # 2. СЦЕНАРИЙ 1: VIP-клиент (если VIP привязан к спец-магазину с кодом [BABYKEA_PREMIUM])
    if mag_promo == "[BABYKEA_PREMIUM]":
        share_promo = "BKEA-4K7X"  # Гостевой промокод (у меня в эксель записан первым)
        caption = (
            f"👑 <b>У вас PREMIUM-доступ!</b>\n\n"
            f"Ваш аккаунт включает 50 запросов к AI-консультанту и глобальный поиск колясок по базам "
            f"магазинов с высокой репутацией. Ваш личный доступ привязан к аккаунту и не может быть передан\n\n"
            f"Но вы можете сделать подарок подруге! Отправьте ей гостевой промокод: <b>{share_promo}</b>\n\n"
            f"Он даст ей базовый бесплатный доступ к полезным материалам, уходу за коляской и "
            f"стандартному функционалу бота\n\n"
            f"{bot_link}"
        )

    # 3. СЦЕНАРИЙ 2: Обычный пользователь (Берем актуальный код магазина)
    elif mag_promo:
        share_promo = mag_promo
        caption = (
            f"Ваш код активации: <b>{share_promo}</b>\n\n"
            f"Вы можете им поделиться со своими друзьями\n\n"
            f"{bot_link}"
        )

    # 4. СЦЕНАРИЙ 3: Магазин не привязан, либо у магазина стерт промокод
    else:
        await message.answer("Ваш промо код истек - им нельзя поделиться")
        return  # Выходим, чтобы не рисовать кнопку и картинку

    # 5. Формируем текст для ДРУГА
    share_text = (
        f"🔍 Ищете коляску?\n"
        f"Подберем надежную модель под ваши условия\n\n"
        f"🛠 Уже купили?\n"
        f"Узнайте, как случайно не сломать её (80% поломок — вина владельцев!)\n\n"
        f"{share_promo} - промокод для бесплатной активации (скопируйте его)"
    )

    # Обязательно кодируем текст для URL
    encoded_text = urllib.parse.quote(share_text)

    # Специальная ссылка Telegram для шаринга
    share_url = f"https://t.me/share/url?url={bot_link}&text={encoded_text}"

    # Создаем кнопку с url-переходом
    share_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↗️ Поделиться ссылкой", url=share_url)]
    ])

    # Отправляем фото с текстом и кнопкой
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
