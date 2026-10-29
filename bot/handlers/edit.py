"""Редактирование напоминания: текст, расписание или интервал предупреждения."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from asgiref.sync import sync_to_async

from bot.keyboards.main import MAIN_MENU, TYPE_KB, remind_before_keyboard
from bot.states import CreateReminder, EditReminder
from bot.utils import humanize_minutes
from calendar_sync.sync import schedule_push
from core.models import MAX_REMINDER_TEXT_LENGTH, Reminder

router = Router()


def _edit_menu_kb(pk: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Изменить текст", callback_data=f"edittext:{pk}")],
            [InlineKeyboardButton(text="⏰ Изменить расписание", callback_data=f"editsched:{pk}")],
            [InlineKeyboardButton(text="⏳ Напомнить заранее", callback_data=f"editrb:{pk}")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="back:list")],
        ]
    )


@router.callback_query(F.data.startswith("editmenu:"))
async def edit_menu(callback: CallbackQuery, state: FSMContext):
    pk = int(callback.data.split(":")[1])
    await state.clear()
    await state.update_data(edit_id=pk)
    await callback.message.edit_text("✏️ Что изменить?", reply_markup=_edit_menu_kb(pk))
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


# ---- интервал предупреждения ----
@router.callback_query(F.data.startswith("editrb:"))
async def edit_remind_before(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    r = await _get(pk)
    current = "по умолчанию" if r.remind_before is None else humanize_minutes(r.remind_before)
    kb = remind_before_keyboard(
        f"rb:edit:{pk}", r.user.default_remind_before, back_callback=f"editmenu:{pk}"
    )
    await callback.message.edit_text(
        f"⏳ Напомнить заранее (сейчас: {current}). Выбери интервал:", reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rb:edit:"))
async def edit_remind_before_set(callback: CallbackQuery):
    parts = callback.data.split(":")
    pk = int(parts[2])
    val = parts[3]
    remind_before = None if val == "default" else int(val)
    await _set_remind_before(pk, remind_before)
    await callback.answer("✅ Сохранено")
    await callback.message.edit_text("✏️ Что изменить?", reply_markup=_edit_menu_kb(pk))


@sync_to_async
def _get(pk: int):
    return Reminder.objects.select_related("user").get(pk=pk)


@sync_to_async
def _set_remind_before(pk: int, minutes: int | None):
    Reminder.objects.filter(pk=pk).update(remind_before=minutes)


@sync_to_async
def _update_text(pk: int, text: str):
    Reminder.objects.filter(pk=pk).update(text=text)
