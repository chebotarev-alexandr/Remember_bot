"""Список напоминаний: просмотр, пауза/возобновление, удаление."""

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from asgiref.sync import sync_to_async

from bot.handlers.common import try_edit
from bot.utils import format_reminder
from core.models import Reminder, TelegramUser

router = Router()

PER_PAGE = 5


@router.message(F.text == "📋 Мои напоминания")
async def list_reminders(message: Message, db_user: TelegramUser):
    text, kb = await _render(db_user.pk, 0)
    await message.answer(text, reply_markup=kb)


@sync_to_async
def _items(user_pk: int):
    return list(
        Reminder.objects.filter(user_id=user_pk, is_deleted=False)
        .select_related("user")
        .order_by("created_at")
    )


@sync_to_async
def _get(pk: int):
    return Reminder.objects.select_related("user").get(pk=pk)


@sync_to_async
def _toggle(pk: int) -> bool:
    r = Reminder.objects.get(pk=pk)
    r.is_active = not r.is_active
    r.save()
    return r.is_active


@sync_to_async
def _delete(pk: int):
    Reminder.objects.filter(pk=pk).update(is_deleted=True)


async def _render(user_pk: int, page: int):
    items = await _items(user_pk)
    if not items:
        return (
            "📭 У тебя пока нет напоминаний.\n\nСоздай первое через ➕ Новое напоминание",
            None,
        )

    total = max(1, (len(items) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, total - 1))
    chunk = items[page * PER_PAGE : (page + 1) * PER_PAGE]

    lines = [f"📋 <b>Мои напоминания</b> ({len(items)}):\n"]
    for i, r in enumerate(chunk, start=page * PER_PAGE + 1):
        status = "" if r.is_active else " ⏸"
        lines.append(f"{i}. {escape(r.text)} — {format_reminder(r)}{status}")
    lines.append(f"\nСтраница {page + 1}/{total}")

    kb = [
        [InlineKeyboardButton(text=f"{i}. {r.text[:30]}", callback_data=f"rem:{r.pk}")]
        for i, r in enumerate(chunk, start=page * PER_PAGE + 1)
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"listpage:{page - 1}"))
    if page < total - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"listpage:{page + 1}"))
    if nav:
        kb.append(nav)

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data.startswith("listpage:"))
async def list_page(callback: CallbackQuery, db_user: TelegramUser):
    page = int(callback.data.split(":")[1])
    text, kb = await _render(db_user.pk, page)
    await try_edit(callback.message, text, kb)
    await callback.answer()


@router.callback_query(F.data == "back:list")
async def back_to_list(callback: CallbackQuery, db_user: TelegramUser):
    text, kb = await _render(db_user.pk, 0)
    await try_edit(callback.message, text, kb)
    await callback.answer()


@router.callback_query(F.data.startswith("rem:"))
async def rem_detail(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    r = await _get(pk)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶ Возобновить" if not r.is_active else "⏸ Поставить на паузу",
                    callback_data=f"toggle:{r.pk}",
                )
            ],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"editmenu:{r.pk}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del:{r.pk}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="back:list")],
        ]
    )
    status = "\n\n⏸ <b>На паузе</b>" if not r.is_active else ""
    await callback.message.edit_text(
        f"📌 <b>{escape(r.text)}</b>\n\n{format_reminder(r)}{status}\n\nЧто сделать?",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle:"))
async def toggle_reminder(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    now_active = await _toggle(pk)
    await callback.answer(f"⏸ Пауза" if not now_active else "▶ Возобновлено")
    # перерисовать детали
    r = await _get(pk)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶ Возобновить" if not r.is_active else "⏸ Поставить на паузу",
                    callback_data=f"toggle:{r.pk}",
                )
            ],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"editmenu:{r.pk}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del:{r.pk}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="back:list")],
        ]
    )
    status = "\n\n⏸ <b>На паузе</b>" if not r.is_active else ""
    await callback.message.edit_text(
        f"📌 <b>{escape(r.text)}</b>\n\n{format_reminder(r)}{status}\n\nЧто сделать?",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("del:"))
async def delete_reminder(callback: CallbackQuery, db_user: TelegramUser):
    pk = int(callback.data.split(":")[1])
    await _delete(pk)
    await callback.answer("🗑 Удалено")
    text, kb = await _render(db_user.pk, 0)
    await try_edit(callback.message, text, kb)
