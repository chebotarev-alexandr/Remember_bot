"""Интерактивный календарь (inline-кнопки)."""

import calendar
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils import MONTH_NAMES

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def calendar_keyboard(year: int, month: int, min_date: date | None = None) -> InlineKeyboardMarkup:
    rows = []

    # Шапка: навигация + месяц/год
    rows.append(
        [
            InlineKeyboardButton(text="◀", callback_data=f"cal:prev:{year}:{month}"),
            InlineKeyboardButton(text=f"{MONTH_NAMES[month - 1]} {year}", callback_data="cal:noop"),
            InlineKeyboardButton(text="▶", callback_data=f"cal:next:{year}:{month}"),
        ]
    )
    # Заголовки дней недели
    rows.append([InlineKeyboardButton(text=w, callback_data="cal:noop") for w in WEEKDAYS])

    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="cal:noop"))
                continue
            d = date(year, month, day)
            if min_date is not None and d < min_date:
                row.append(InlineKeyboardButton(text=" ", callback_data="cal:noop"))
            else:
                row.append(
                    InlineKeyboardButton(text=str(day), callback_data=f"cal:pick:{year}:{month}:{day}")
                )
        rows.append(row)

    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
