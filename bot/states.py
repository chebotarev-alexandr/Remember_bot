"""FSM-состояния бота."""

from aiogram.fsm.state import State, StatesGroup


class CreateReminder(StatesGroup):
    text = State()
    type = State()
    date = State()  # для однократного — выбор даты
    hour = State()
    minute = State()
    frequency = State()  # для регулярного — daily/weekly/monthly
    weekday = State()  # для weekly
    day_of_month = State()  # для monthly
    confirm = State()


class SetTimezone(StatesGroup):
    choose = State()
