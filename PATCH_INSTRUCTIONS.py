"""
=== ПАТЧ-ИНСТРУКЦИЯ для app/platforms/vk/handlers/user_handlers.py ===
Все замены делать в PyCharm через Ctrl+H (Replace) или вручную.
Номера строк приблизительные — ориентируйся на содержимое.
"""

# ============================================================
# ЗАМЕНА 1: handle_message_event — передаём conversation_message_id
# ============================================================

# НАЙДИ (строка ~144):
"""
async def handle_message_event(event: dict, vk_api: API, sm):
    \"\"\"Обрабатывает нажатие inline-кнопки (message_event).\"\"\"
    vk_id = event.get("user_id")
    peer_id = event.get("peer_id", vk_id)
    payload = event.get("payload", {})
    event_id = event.get("event_id")
    cmd = payload.get("cmd", "")

    if not vk_id:
        return

    # Подтверждаем событие (убирает спиннер с кнопки)
    with contextlib.suppress(Exception):
        await vk_api.messages.send_message_event_answer(
            event_id=event_id, user_id=vk_id, peer_id=peer_id,
        )

    async with sm() as session:
        user = await get_or_create_user_vk(session, vk_id)
        await _handle_command(cmd, vk_id, peer_id, user, session, vk_api, sm)
"""

# ЗАМЕНИ НА:
"""
async def handle_message_event(event: dict, vk_api: API, sm):
    \"\"\"Обрабатывает нажатие Callback-кнопки (message_event).\"\"\"
    vk_id = event.get("user_id")
    peer_id = event.get("peer_id", vk_id)
    payload = event.get("payload", {})
    event_id = event.get("event_id")
    conversation_message_id = event.get("conversation_message_id")
    cmd = payload.get("cmd", "")

    if not vk_id:
        return

    # Подтверждаем событие (убирает спиннер с Callback-кнопки)
    with contextlib.suppress(Exception):
        await vk_api.messages.send_message_event_answer(
            event_id=event_id, user_id=vk_id, peer_id=peer_id,
        )

    async with sm() as session:
        user = await get_or_create_user_vk(session, vk_id)
        await _handle_command(cmd, vk_id, peer_id, user, session, vk_api, sm,
                              conversation_message_id=conversation_message_id)
"""


# ============================================================
# ЗАМЕНА 2: _handle_command — добавить conversation_message_id
# ============================================================

# НАЙДИ (строка ~170):
"""
async def _handle_command(cmd, vk_id, peer_id, user, session, vk_api, sm=None):
"""

# ЗАМЕНИ НА:
"""
async def _handle_command(cmd, vk_id, peer_id, user, session, vk_api, sm=None,
                          conversation_message_id=None):
"""

# А ТАКЖЕ внутри _handle_command НАЙДИ все elif для квиза и замени:

# НАЙДИ:
"""
    elif cmd == "quiz:start":
        await _handle_quiz_start(vk_id, peer_id, session, vk_api)

    elif cmd and cmd.startswith("quiz:select:"):
        option = cmd.split(":")[2]
        await _handle_quiz_select(vk_id, peer_id, option, session, vk_api)

    elif cmd == "quiz:next":
        await _handle_quiz_next(vk_id, peer_id, session, vk_api)

    elif cmd == "quiz:back":
        await _handle_quiz_back(vk_id, peer_id, session, vk_api)

    elif cmd == "quiz:restore":
        await _handle_quiz_start(vk_id, peer_id, session, vk_api)
"""

# ЗАМЕНИ НА:
"""
    elif cmd == "quiz:start":
        await _handle_quiz_start(vk_id, peer_id, session, vk_api, conversation_message_id)

    elif cmd and cmd.startswith("quiz:select:"):
        option = cmd.split(":")[2]
        await _handle_quiz_select(vk_id, peer_id, option, session, vk_api, conversation_message_id)

    elif cmd == "quiz:next":
        await _handle_quiz_next(vk_id, peer_id, session, vk_api, conversation_message_id)

    elif cmd == "quiz:back":
        await _handle_quiz_back(vk_id, peer_id, session, vk_api, conversation_message_id)

    elif cmd == "quiz:restore":
        await _handle_quiz_start(vk_id, peer_id, session, vk_api, conversation_message_id)
"""


# ============================================================
# ЗАМЕНА 3: ВСЕ квиз-функции — полная замена блока (строки ~872-970)
# ============================================================

# НАЙДИ ВЕСЬ БЛОК от "async def _handle_quiz_start" до конца "_render_quiz_step_vk"
# и ЗАМЕНИ на код ниже:

"""
# ============================================================
# КВИЗ — с messages.edit (как в Telegram)
# ============================================================

def _get_quiz_photo_vk(step: dict, selected: str | None = None) -> str | None:
    \"\"\"Получает VK photo attachment для шага квиза.\"\"\"
    if selected:
        option = step["options"].get(selected)
        if option and "preview" in option:
            return option["preview"].get("photo_vk")
    return step.get("photo_vk")


def _get_quiz_text_vk(step: dict, selected: str | None = None) -> str:
    \"\"\"Получает текст для VK (plain text, без HTML).\"\"\"
    if selected:
        option = step["options"].get(selected)
        if option and "preview" in option:
            return option["preview"].get("text_vk") or _strip_html(option["preview"].get("text", ""))
    return step.get("text_vk") or _strip_html(step.get("text", ""))


async def _handle_quiz_start(vk_id, peer_id, session, vk_api, cmid=None):
    \"\"\"Старт/рестарт квиза — отправляем НОВОЕ сообщение.\"\"\"
    user = await get_or_create_user_vk(session, vk_id)
    profile = await get_or_create_quiz_profile(session, user)

    # Сбрасываем прогресс
    profile.branch = None
    profile.current_level = 1
    profile.completed = False
    profile.completed_once = False
    profile.data = {}
    session.add(profile)
    await session.commit()

    # Удаляем старое сообщение с кнопками (если было)
    if cmid:
        await _edit(vk_api, peer_id, cmid, "⏳ Загрузка квиза...")

    # Отправляем НОВОЕ сообщение (первый шаг квиза)
    await _render_quiz_step_vk(vk_api, peer_id, profile, session=session, send_new=True)


async def _handle_quiz_select(vk_id, peer_id, option, session, vk_api, cmid=None):
    \"\"\"Выбор варианта — РЕДАКТИРУЕМ текущее сообщение.\"\"\"
    user = await get_or_create_user_vk(session, vk_id)
    profile = await get_or_create_quiz_profile(session, user)

    profile.data["_selected"] = option
    session.add(profile)
    await session.commit()

    # Редактируем сообщение — меняем текст и кнопки
    await _render_quiz_step_vk(vk_api, peer_id, profile, selected=option, cmid=cmid, session=session)


async def _handle_quiz_next(vk_id, peer_id, session, vk_api, cmid=None):
    \"\"\"Кнопка «Далее» — переход на следующий шаг.\"\"\"
    user = await get_or_create_user_vk(session, vk_id)
    profile = await get_or_create_quiz_profile(session, user)

    step = get_current_step(profile)
    selected = profile.data.get("_selected")

    if not validate_next(selected):
        await _send(vk_api, peer_id, "⚠️ Выберите вариант, затем нажмите «Далее»")
        return

    await save_and_next(session=session, profile=profile, step=step, selected_option=selected)
    profile.data.pop("_selected", None)
    session.add(profile)
    await session.commit()

    if profile.completed:
        # Убираем кнопки со старого сообщения
        if cmid:
            await _edit(vk_api, peer_id, cmid, "✅ Квиз завершён!")

        if profile.completed_once:
            await _send(vk_api, peer_id,
                        "✅ Квиз завершён\\n\\nВаши ответы обновлены.",
                        keyboard=vk_kb.ai_mode_kb())
            return

        profile.completed_once = True
        session.add(profile)
        await session.commit()

        await _send(
            vk_api, peer_id,
            "✅ Отлично! Квиз-опрос завершён\\n\\n"
            "Теперь у меня есть понимание ситуации. Данные помогут "
            "подбирать модели именно под ваши условия.\\n\\n"
            "Остался последний шаг — открыть доступ к подбору и рекомендациям",
            keyboard=vk_kb.activation_kb(),
        )
        return

    # Переход на следующий шаг — НОВОЕ сообщение (т.к. может быть новое фото)
    # Убираем кнопки со старого сообщения
    if cmid:
        await _edit(vk_api, peer_id, cmid, _get_quiz_text_vk(step, selected))

    await _render_quiz_step_vk(vk_api, peer_id, profile, session=session, send_new=True)


async def _handle_quiz_back(vk_id, peer_id, session, vk_api, cmid=None):
    \"\"\"Кнопка «Назад».\"\"\"
    user = await get_or_create_user_vk(session, vk_id)
    profile = await get_or_create_quiz_profile(session, user)
    await go_back(session, profile)

    # Убираем кнопки со старого, отправляем новое
    if cmid:
        branch = profile.branch or "root"
        try:
            step = QUIZ_CONFIG[branch][profile.current_level]
            await _edit(vk_api, peer_id, cmid, _get_quiz_text_vk(step))
        except KeyError:
            pass

    await _render_quiz_step_vk(vk_api, peer_id, profile, session=session, send_new=True)


async def _handle_quiz_restart(vk_id, peer_id, session, vk_api):
    \"\"\"Аналог /quiz_restart.\"\"\"
    await _handle_quiz_start(vk_id, peer_id, session, vk_api)


async def _render_quiz_step_vk(vk_api, peer_id, profile, selected=None,
                                cmid=None, session=None, send_new=False):
    \"\"\"Рендерит шаг квиза для VK.

    cmid — conversation_message_id для редактирования.
    send_new=True — отправить новым сообщением (для смены фото).
    \"\"\"
    try:
        branch = profile.branch or "root"
        step = QUIZ_CONFIG[branch][profile.current_level]
    except KeyError:
        await _send(vk_api, peer_id, "❌ Ошибка квиза. Попробуйте заново.",
                    keyboard=vk_kb.quiz_start_kb())
        return

    text = _get_quiz_text_vk(step, selected)
    keyboard = vk_kb.build_quiz_keyboard(step, profile, selected)
    photo_vk = _get_quiz_photo_vk(step, selected)

    if cmid and not send_new:
        # РЕДАКТИРУЕМ существующее сообщение (выбор варианта)
        await _edit(vk_api, peer_id, cmid, text, keyboard=keyboard, attachment=photo_vk)
    else:
        # ОТПРАВЛЯЕМ новое сообщение (новый шаг, новое фото)
        await _send(vk_api, peer_id, text, keyboard=keyboard, attachment=photo_vk)
"""


# ============================================================
# ЗАМЕНА 4: Добавить функцию _edit (ПЕРЕД функцией _send)
# ============================================================

# ПЕРЕД строкой "async def _send(..." ДОБАВЬ:

"""
async def _edit(vk_api: API, peer_id: int, conversation_message_id: int,
                text: str, keyboard: str = None, attachment: str = None):
    \"\"\"Редактирует сообщение бота в VK (аналог edit_message в Telegram).\"\"\"
    try:
        kwargs = {
            "peer_id": peer_id,
            "conversation_message_id": conversation_message_id,
            "message": text or " ",
        }
        if keyboard:
            kwargs["keyboard"] = keyboard
        if attachment:
            kwargs["attachment"] = attachment

        await vk_api.messages.edit(**kwargs)
    except Exception as e:
        logger.error(f"VK edit error (cmid={conversation_message_id}): {e}")
"""
