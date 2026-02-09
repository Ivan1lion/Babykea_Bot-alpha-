from aiogram.fsm.state import State, StatesGroup

class MenuStates(StatesGroup):
    waiting_for_email = State()