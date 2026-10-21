"""Общие хелперы обработчиков."""

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message


async def try_edit(message: Message, text: str, reply_markup=None) -> None:
    """Редактирует сообщение, молча пропуская «not modified», с fallback на answer."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            await message.answer(text, reply_markup=reply_markup)
