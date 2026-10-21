"""Редактирование напоминания: текст или расписание."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from asgiref.sync import sync_to_async

from bot.keyboards.main import MAIN_MENU, TYPE_KB
from bot.states import CreateReminder, EditReminder
from calendar_sync.sync import schedule_push
from core.models import MAX_REMINDER_TEXT_LENGTH, Reminder

router = Router()


@router.callback_query(F.data.startswith("editmenu:"))
async def edit_menu(callback: CallbackQuery, state: FSMContext):
    pk = int(callback.data.split(":")[1])
    await state.clear()
    await state.update_data(edit_id=pk)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Изменить текст", callback_data=f"edittext:{pk}")],
            [InlineKeyboardButton(text="⏰ Изменить расписание", callback_data=f"editsched:{pk}")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="back:list")],
        ]
    )
    await callback.message.edit_text("✏️ Что изменить?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("edittext:"))
async def edit_text(callback: CallbackQuery, state: FSMContext):
    pk = int(callback.data.split(":")[1])
    await state.update_data(edit_id=pk)
    await state.set_state(EditReminder.text)
    await callback.message.edit_text("✏️ Напиши новый текст напоминания:")
    await callback.answer()


@router.message(EditReminder.text, F.text)
async def edit_text_input(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) > MAX_REMINDER_TEXT_LENGTH:
        await message.answer(
            f"⚠️ Слишком длинно (макс. {MAX_REMINDER_TEXT_LENGTH:,} символов). Напиши короче:"
        )
        return
    data = await state.get_data()
    await _update_text(data["edit_id"], text)
    await schedule_push(data["edit_id"])
    await state.clear()
    await message.answer("✅ Текст обновлён.", reply_markup=MAIN_MENU)


@router.callback_query(F.data.startswith("editsched:"))
async def edit_schedule(callback: CallbackQuery, state: FSMContext):
    pk = int(callback.data.split(":")[1])
    await state.update_data(edit_id=pk)
    await state.set_state(CreateReminder.type)
    await callback.message.edit_text("Какое напоминание?", reply_markup=TYPE_KB)
    await callback.answer()


@sync_to_async
def _update_text(pk: int, text: str):
    Reminder.objects.filter(pk=pk).update(text=text)
