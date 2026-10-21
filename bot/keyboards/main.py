"""Клавиатуры: главное меню, выбор типа/частоты/дня."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Новое напоминание"), KeyboardButton(text="📋 Мои напоминания")],
        [KeyboardButton(text="🌍 Часовой пояс"), KeyboardButton(text="⭐ Премиум")],
        [KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
)

TYPE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Однократное", callback_data="type:once")],
        [InlineKeyboardButton(text="🔁 Регулярное", callback_data="type:regular")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ]
)

FREQUENCY_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ежедневно", callback_data="freq:daily")],
        [InlineKeyboardButton(text="📆 Еженедельно", callback_data="freq:weekly")],
        [InlineKeyboardButton(text="🗓 Ежемесячно", callback_data="freq:monthly")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="back:type")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ]
)


def weekday_keyboard(selected: set[int] | None = None):
    from bot.utils import WEEKDAY_NAMES

    selected = selected or set()
    row = [
        InlineKeyboardButton(
            text=("✅ " + name) if i in selected else name,
            callback_data=f"wd:toggle:{i}",
        )
        for i, name in enumerate(WEEKDAY_NAMES)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            row,
            [InlineKeyboardButton(text="✅ Готово", callback_data="wd:done")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="back:freq")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def day_of_month_keyboard():
    rows = []
    for start in range(1, 32, 7):
        rows.append(
            [
                InlineKeyboardButton(text=str(d), callback_data=f"dom:{d}")
                for d in range(start, min(start + 7, 32))
            ]
        )
    rows.append([InlineKeyboardButton(text="◀ Назад", callback_data="back:freq")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data="confirm:yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="confirm:no"),
            ]
        ]
    )
