"""Интерактивный выбор времени (часы → минуты)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def hours_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for start in range(0, 24, 6):
        rows.append(
            [
                InlineKeyboardButton(text=f"{h:02d}", callback_data=f"time:h:{h}")
                for h in range(start, start + 6)
            ]
        )
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def minutes_keyboard() -> InlineKeyboardMarkup:
    minutes = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
    rows = []
    for start in range(0, 12, 4):
        rows.append(
            [
                InlineKeyboardButton(text=f"{m:02d}", callback_data=f"time:m:{m}")
                for m in minutes[start : start + 4]
            ]
        )
    rows.append([InlineKeyboardButton(text="◀ Назад", callback_data="time:back")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
