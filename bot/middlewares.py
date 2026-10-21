"""Middleware: регистрация пользователя + проверка блокировки."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from asgiref.sync import sync_to_async

from core.models import TelegramUser


@sync_to_async
def _get_or_create_user(telegram_id, username, first_name, last_name):
    user, _ = TelegramUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            "username": username or "",
            "first_name": first_name or "",
            "last_name": last_name or "",
        },
    )
    dirty = False
    if username and user.username != username:
        user.username = username
        dirty = True
    if user.first_name != (first_name or ""):
        user.first_name = first_name or ""
        dirty = True
    if user.last_name != (last_name or ""):
        user.last_name = last_name or ""
        dirty = True
    if dirty:
        user.save()
    return user


class UserMiddleware(BaseMiddleware):
    """Регистрирует пользователя и отсекает заблокированных."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if tg_user is not None:
            user = await _get_or_create_user(
                tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name
            )
            if user.is_blocked:
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer("⛔ Вы заблокированы.", show_alert=True)
                    except Exception:
                        pass
                elif isinstance(event, Message):
                    await event.answer("⛔ Вы заблокированы.")
                return None
            data["db_user"] = user

        return await handler(event, data)
