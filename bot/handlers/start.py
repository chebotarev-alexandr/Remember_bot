"""Обработчики: /start, /help, главное меню."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards.main import MAIN_MENU
from core.models import TelegramUser

router = Router()


WELCOME = (
    "👋 Привет! Я бот-напоминалка.\n\n"
    "Помогу не забыть важное:\n"
    "• ⏰ однократные напоминания на конкретную дату\n"
    "• 🔁 регулярные: ежедневно, еженедельно, ежемесячно\n\n"
    "Бесплатно — до 10 регулярных и 3 однократных напоминаний. "
    "⭐ Премиум снимает лимиты."
)


@router.message(CommandStart())
async def start(message: Message, db_user: TelegramUser):
    await message.answer(WELCOME, reply_markup=MAIN_MENU)
    if db_user.timezone == "UTC":
        await message.answer(
            "🌍 Похоже, ты ещё не выбрал часовой пояс — без него напоминания "
            "будут приходить не вовремя.\n\nНажми «🌍 Часовой пояс» и выбери свой город.",
        )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(help_text(), reply_markup=MAIN_MENU)


@router.message(F.text == "ℹ️ Помощь")
async def help_button(message: Message):
    await message.answer(help_text(), reply_markup=MAIN_MENU)


def help_text() -> str:
    return (
        "ℹ️ Как пользоваться:\n\n"
        "➕ <b>Новое напоминание</b> — создай напоминание. Сначала текст, "
        "затем тип (однократное или регулярное), затем дата/время или частота.\n\n"
        "📋 <b>Мои напоминания</b> — список, где можно удалить или поставить на паузу.\n\n"
        "🌍 <b>Часовой пояс</b> — выбери свой город, чтобы напоминания приходили вовремя.\n\n"
        "⭐ <b>Премиум</b> — безлимитные напоминания.\n\n"
        "Команды: /start, /help"
    )
