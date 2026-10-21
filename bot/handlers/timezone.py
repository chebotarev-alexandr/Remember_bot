"""Обработчик выбора часового пояса."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from bot.keyboards.timezone import timezone_keyboard
from bot.states import SetTimezone
from bot.utils import tz_label
from core.models import TelegramUser

router = Router()


@router.message(F.text == "🌍 Часовой пояс")
async def timezone_menu(message: Message, state: FSMContext, db_user: TelegramUser):
    await state.set_state(SetTimezone.choose)
    await message.answer(
        f"🌍 Текущий пояс: <b>{tz_label(db_user.timezone)}</b>\n\nВыбери новый:",
        reply_markup=timezone_keyboard(),
    )


@router.callback_query(SetTimezone.choose, F.data.startswith("tzpage:"))
async def tz_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "🌍 Выбери часовой пояс:", reply_markup=timezone_keyboard(page)
    )
    await callback.answer()


@router.callback_query(SetTimezone.choose, F.data == "tz:noop")
async def tz_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(SetTimezone.choose, F.data.startswith("tz:"))
async def tz_pick(callback: CallbackQuery, state: FSMContext, db_user: TelegramUser):
    name = callback.data.split(":", 1)[1]
    await _save_tz(db_user.pk, name)
    await state.clear()
    await callback.message.edit_text(f"✅ Часовой пояс: <b>{tz_label(name)}</b>")
    await callback.answer()


@sync_to_async
def _save_tz(user_pk: int, tz_name: str):
    TelegramUser.objects.filter(pk=user_pk).update(timezone=tz_name)
