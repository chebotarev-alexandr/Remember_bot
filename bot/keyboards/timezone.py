"""Интерактивный выбор часового пояса (пагинация)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils import COMMON_TIMEZONES

PER_PAGE = 6


def timezone_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    total = len(COMMON_TIMEZONES)
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * PER_PAGE
    items = COMMON_TIMEZONES[start : start + PER_PAGE]

    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"tz:{name}")] for name, label in items
    ]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"tzpage:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="tz:noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"tzpage:{page + 1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
