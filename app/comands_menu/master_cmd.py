import logging
import contextlib
import json

from aiogram import Router, Bot, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto,
)
from aiogram.filters import Command, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import closed_menu

logger = logging.getLogger(__name__)

master_router = Router()

# ID канала для пересылки обращений
MASTER_CHANNEL_ID = -1003569512456

MAX_PHOTOS = 5  # Максимальное количество фото в альбоме


# ==========================================
# FSM
# ==========================================
class MasterFeedbackState(StatesGroup):
    choosing_type   = State()  # Шаг 1: выбор типа обращения
    waiting_media   = State()  # Шаг 2: ждём фото/видео
    waiting_text    = State()  # Шаг 3: ждём текст обращения


# ==========================================
# КЛАВИАТУРЫ
# ==========================================
start_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💬 Поделиться историей", callback_data="mf_start")], # Первая строка
    [InlineKeyboardButton(text="❌ Отмена", callback_data="mf_cancel")]          # Вторая строка
])

type_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📸 Пришлю с фото/видео", callback_data="mf_with_media")],
    [InlineKeyboardButton(text="💬 Просто напишу текст", callback_data="mf_no_media")],
])

no_text_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➡️ Отправить без текста", callback_data="mf_no_text")],
])


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def _user_info(user) -> str:
    """Строка с данными юзера для подписи в канале."""
    username = f"@{user.username}" if user.username else "нет username"
    return f"👤 ID: <code>{user.id}</code> | {username}"


async def _delete_prompt(bot: Bot, chat_id: int, state: FSMContext):
    """Удаляет сообщение с кнопками (промпт), сохранённое в FSM."""
    data = await state.get_data()
    msg_id = data.get("prompt_msg_id")
    if msg_id:
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)


async def _send_to_channel(bot: Bot, user, photo_ids: list, video_id: str | None, text: str | None):
    """
    Формирует и отправляет итоговое сообщение в канал.

    Варианты:
      - только текст
      - одно фото + текст
      - альбом (2-5 фото) — подпись крепится к последнему элементу (ограничение Telegram API)
      - видео + текст
    """
    user_line = _user_info(user)
    caption = f"{text}\n\n{user_line}" if text else user_line

    # --- Только текст ---
    if not photo_ids and not video_id:
        await bot.send_message(chat_id=MASTER_CHANNEL_ID, text=caption)
        return

    # --- Одно фото ---
    if len(photo_ids) == 1:
        await bot.send_photo(
            chat_id=MASTER_CHANNEL_ID,
            photo=photo_ids[0],
            caption=caption
        )
        return

    # --- Альбом (2-5 фото) ---
    if len(photo_ids) > 1:
        media = []
        for i, file_id in enumerate(photo_ids):
            # Подпись только у последнего элемента — ограничение Telegram
            item_caption = caption if i == len(photo_ids) - 1 else None
            media.append(InputMediaPhoto(media=file_id, caption=item_caption))
        await bot.send_media_group(chat_id=MASTER_CHANNEL_ID, media=media)
        return

    # --- Видео ---
    if video_id:
        await bot.send_video(
            chat_id=MASTER_CHANNEL_ID,
            video=video_id,
            caption=caption
        )


# ==========================================
# 0. КОМАНДА /master26
# ==========================================
@master_router.message(or_f(Command("master26"), F.text.lower() == "master26"))
async def master_cmd(message: Message, state: FSMContext, session: AsyncSession):
    if await closed_menu(message=message, session=session):
        return
    # Сбрасываем предыдущее состояние если юзер повторно нажал команду
    await state.clear()
    await state.set_state(MasterFeedbackState.choosing_type)

    prompt = await message.answer(
        text="📬 <b>Код принят. Прямая линия открыта</b>\n\n"
             "Сюда можно присылать не только вопросы по ремонту. Муки выбора между двумя крутыми моделями? "
             "Родственники отдают старую коляску, и нужен честный взгляд со стороны? Вас обманули в магазине и вы хотите "
             "придать это огласке? А может, просто желаете похвастаться удачной покупкой?\n\n"
             "Пишите, кидайте фото или видео. Лучшие темы я беру для разборов и голосований в канале!\n\n"
             "Нажмите <b>«💬 Поделиться историей»</b> чтобы начать:",
        reply_markup=start_kb
    )
    await state.update_data(prompt_msg_id=prompt.message_id)


# ==========================================
# 1. ОТМЕНА (из любого состояния формы)
# ==========================================
@master_router.callback_query(
    F.data == "mf_cancel",
    StateFilter(
        MasterFeedbackState.choosing_type,
        MasterFeedbackState.waiting_media,
        MasterFeedbackState.waiting_text,
    )
)
async def master_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    with contextlib.suppress(Exception):
        await call.message.delete()
    await call.message.answer("👌 <b>Без проблем, отменил</b>"
                              "\n\nГлавное меню снова активно. Если появится интересная история, сложный выбор или "
                              "тема для разбора в канале — вы знаете, какую команду ввести 😉")
    await call.answer()


# ==========================================
# 2. "Написать обращение" — шаг выбора типа
# ==========================================
@master_router.callback_query(F.data == "mf_start", StateFilter(MasterFeedbackState.choosing_type))
async def master_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(MasterFeedbackState.choosing_type)

    # Удаляем предыдущее сообщение с кнопками
    with contextlib.suppress(Exception):
        await call.message.delete()

    prompt = await call.message.answer(
        text="👀 <b>Жду вашу историю!</b>\n\n"
             "К тексту можно прикрепить <b>до 5 фото или 1 видео</b>. Выбирайте, как будем отправлять",
        reply_markup=type_kb
    )
    await state.update_data(prompt_msg_id=prompt.message_id)
    await call.answer()


# ==========================================
# 3а. "Обращение без фото/видео" — сразу ждём текст
# ==========================================
@master_router.callback_query(F.data == "mf_no_media", StateFilter(MasterFeedbackState.choosing_type))
async def master_no_media(call: CallbackQuery, state: FSMContext):
    await state.set_state(MasterFeedbackState.waiting_text)

    with contextlib.suppress(Exception):
        await call.message.delete()

    prompt = await call.message.answer(
        text="<b>Договорились, только текст</b>"
             "\n\nОпишите ситуацию во всех подробностях: что случилось, в чем сомнения или чем хотите поделиться. "
             "Напишите всё одним сообщением и отправляйте 👇",
    )
    await state.update_data(prompt_msg_id=prompt.message_id, photo_ids=[], video_id=None)
    await call.answer()


# ==========================================
# 3б. "Загрузить фото/видео" — ждём медиа
# ==========================================
@master_router.callback_query(F.data == "mf_with_media", StateFilter(MasterFeedbackState.choosing_type))
async def master_with_media(call: CallbackQuery, state: FSMContext):
    await state.set_state(MasterFeedbackState.waiting_media)

    with contextlib.suppress(Exception):
        await call.message.delete()

    prompt = await call.message.answer(
        text=f"🖼 <b>Пришлите фото (до {MAX_PHOTOS} штук) или одно видео</b>\n\n"
             f"<i>Фото можно отправить одним альбомом или по одному.</i>",
    )
    await state.update_data(prompt_msg_id=prompt.message_id, photo_ids=[], video_id=None)
    await call.answer()


# ==========================================
# 4а. ПРИЁМ ФОТО (одиночное или из альбома)
# ==========================================
@master_router.message(StateFilter(MasterFeedbackState.waiting_media), F.photo)
async def handle_photo(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    photo_ids: list = data.get("photo_ids", [])

    # Берём наибольшее разрешение (последний элемент списка)
    file_id = message.photo[-1].file_id

    if len(photo_ids) >= MAX_PHOTOS:
        await message.delete()
        await message.answer(
            f"📸 Места для фото больше нет (максимум {MAX_PHOTOS})"
            f"\n\nТеперь опишите ситуацию одним сообщением и отправьте его мне или нажмите кнопку ниже",
            reply_markup=no_text_kb
        )
        return

    photo_ids.append(file_id)
    await state.update_data(photo_ids=photo_ids)

    # Удаляем сообщение юзера с фото — накапливаем file_id, не захламляем чат
    await message.delete()

    # Когда набрали MAX_PHOTOS — автоматически переходим к тексту
    if len(photo_ids) >= MAX_PHOTOS:
        await _delete_prompt(bot, message.chat.id, state)
        await state.set_state(MasterFeedbackState.waiting_text)
        prompt = await message.answer(
            f"✅ {MAX_PHOTOS} фото получено!\n\n"
            f"Теперь расскажите, в чем суть: что сломалось, между чем выбираем или чем хвастаемся?"
            f"\n\nНапишите всё в одном сообщении и отправьте его мне или нажмите кнопку ниже",
            reply_markup=no_text_kb
        )
        await state.update_data(prompt_msg_id=prompt.message_id)
    else:
        remaining = MAX_PHOTOS - len(photo_ids)
        # Обновляем промпт с подсчётом
        data = await state.get_data()
        with contextlib.suppress(Exception):
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=data.get("prompt_msg_id"),
                text=f"🖼 Получено фото: {len(photo_ids)}/{MAX_PHOTOS}.\n\n"
                     f"Можете докинуть ещё {remaining} или нажмите кнопку ниже",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✍️ Добавить текст", callback_data="mf_media_done")]
                ])
            )


# ==========================================
# 4б. ПРИЁМ ВИДЕО
# ==========================================
@master_router.message(StateFilter(MasterFeedbackState.waiting_media), F.video)
async def handle_video(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()

    # Если уже есть фото — не разрешаем смешивать
    if data.get("photo_ids"):
        await message.delete()
        await message.answer("⚠️ Вы уже добавили фото. Нельзя смешивать фото и видео"
                             "\n\nПродолжайте добавлять фото или перейдите к тексту")
        return

    await message.delete()
    await state.update_data(video_id=message.video.file_id)
    await _delete_prompt(bot, message.chat.id, state)
    await state.set_state(MasterFeedbackState.waiting_text)

    prompt = await message.answer(
        "✅ <b>Видео получено!</b>\n\n"
        "Добавьте пару слов для контекста: суть проблемы или ваш вопрос"
        "\n\nНапишите всё в одном сообщении и отправьте его мне или нажмите кнопку ниже",
        reply_markup=no_text_kb
    )
    await state.update_data(prompt_msg_id=prompt.message_id)


# ==========================================
# 4в. "Перейти к тексту" — когда юзер добавил фото и хочет идти дальше
# ==========================================
@master_router.callback_query(F.data == "mf_media_done", StateFilter(MasterFeedbackState.waiting_media))
async def master_media_done(call: CallbackQuery, state: FSMContext):
    await state.set_state(MasterFeedbackState.waiting_text)

    with contextlib.suppress(Exception):
        await call.message.delete()

    prompt = await call.message.answer(
        "Добавьте пару слов для контекста: суть проблемы или ваш вопрос"
        "\n\nНапишите всё в одном сообщении и отправьте его мне или нажмите кнопку ниже",
        reply_markup=no_text_kb
    )
    await state.update_data(prompt_msg_id=prompt.message_id)
    await call.answer()


# ==========================================
# 4г. НЕДОПУСТИМЫЙ КОНТЕНТ в режиме ожидания медиа
#     (гифки, голосовые, стикеры, текст и т.д.)
# ==========================================
@master_router.message(
    StateFilter(MasterFeedbackState.waiting_media),
    ~F.photo,
    ~F.video,
)
async def handle_wrong_media(message: Message):
    await message.delete()
    await message.answer(
        f"⚠️ Допускается только фото (до {MAX_PHOTOS} штук) или одно видео.\n\n"
        f"Повторите отправку"
    )


# ==========================================
# 5а. "Отправить без текста"
# ==========================================
@master_router.callback_query(F.data == "mf_no_text", StateFilter(MasterFeedbackState.waiting_text))
async def master_no_text(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    with contextlib.suppress(Exception):
        await call.message.delete()

    await _send_to_channel(
        bot=bot,
        user=call.from_user,
        photo_ids=data.get("photo_ids", []),
        video_id=data.get("video_id"),
        text=None
    )

    await state.clear()
    await call.message.answer(
        "✅ <b>Послание отправлено!</b>\n\n"
        "Если это тот самый случай, на котором стоит поучиться остальным, или просто классная история — скоро обсудим "
        "её в канале! Спасибо 👍"
    )
    await call.answer()


# ==========================================
# 5б. ПРИЁМ ТЕКСТА ОБРАЩЕНИЯ
# ==========================================
@master_router.message(StateFilter(MasterFeedbackState.waiting_text), F.text)
async def handle_text(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()

    await _delete_prompt(bot, message.chat.id, state)
    await message.delete()

    await _send_to_channel(
        bot=bot,
        user=message.from_user,
        photo_ids=data.get("photo_ids", []),
        video_id=data.get("video_id"),
        text=message.text
    )

    await state.clear()
    await message.answer(
        "✅ <b>Послание отправлено!</b>\n\n"
        "Если это тот самый случай, на котором стоит поучиться остальным, или просто классная история — скоро обсудим "
        "её в канале! Спасибо 👍"
    )


# ==========================================
# 5в. НЕДОПУСТИМЫЙ КОНТЕНТ в режиме ожидания текста
# ==========================================
@master_router.message(StateFilter(MasterFeedbackState.waiting_text), ~F.text)
async def handle_wrong_text(message: Message):
    await message.delete()
    await message.answer("⚠️ Пожалуйста, отправьте текстовое сообщение")