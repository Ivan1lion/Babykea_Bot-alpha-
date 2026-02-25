from aiogram.fsm.state import State, StatesGroup

class MenuStates(StatesGroup):
    waiting_for_email = State()


class ServiceState(StatesGroup):
    waiting_for_model = State()  # Состояние: ждем ввода модели коляски