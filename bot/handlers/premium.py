"""Обработчик раздела «Премиум»."""

from aiogram import F, Router
from aiogram.types import Message

from bot.limits import limits_summary
from core.models import TelegramUser

router = Router()


@router.message(F.text == "⭐ Премиум")
async def premium(message: Message, db_user: TelegramUser):
    await message.answer(
        f"{limits_summary(db_user)}\n\n"
        "⭐ <b>Премиум</b> — безлимитные напоминания (регулярные и однократные).\n\n"
        "Чтобы подключить премиум, напишите администратору бота.",
    )
