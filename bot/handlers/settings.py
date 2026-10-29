"""Глобальные настройки пользователя (интервал предупреждения по умолчанию)."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from bot.keyboards.main import remind_before_keyboard, settings_keyboard
from bot.utils import humanize_minutes
from core.models import TelegramUser

router = Router()


def _settings_text(user: TelegramUser) -> str:
    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"⏰ Напомнить заранее (по умолчанию): <b>{humanize_minutes(user.default_remind_before)}</b>\n"
        "Применяется к напоминаниям, у которых не задан свой интервал."
    )


@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message, db_user: TelegramUser):
    await message.answer(_settings_text(db_user), reply_markup=settings_keyboard())


@router.callback_query(F.data == "settings:remind_before")
async def settings_remind_before(callback: CallbackQuery, db_user: TelegramUser):
    kb = remind_before_keyboard("rb:global", show_default=False, back_callback="settings:back")
    await callback.message.edit_text(
        "⏰ За сколько напоминать заранее (по умолчанию)?", reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "settings:back")
async def settings_back(callback: CallbackQuery, db_user: TelegramUser):
    await callback.message.edit_text(_settings_text(db_user), reply_markup=settings_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("rb:global:"))
async def settings_remind_before_set(callback: CallbackQuery, db_user: TelegramUser):
    minutes = int(callback.data.split(":")[2])
    await _save_default_remind_before(db_user.pk, minutes)
    user = await _get_user(db_user.pk)
    await callback.message.edit_text(_settings_text(user), reply_markup=settings_keyboard())
    await callback.answer("✅ Сохранено")


@sync_to_async
def _save_default_remind_before(user_pk: int, minutes: int):
    TelegramUser.objects.filter(pk=user_pk).update(default_remind_before=minutes)


@sync_to_async
def _get_user(user_pk: int):
    return TelegramUser.objects.get(pk=user_pk)
