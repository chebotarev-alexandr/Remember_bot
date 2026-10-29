"""Создание напоминания — многошаговый интерактивный флоу."""

from datetime import datetime, time as dt_time, timezone as dt_timezone
from html import escape
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async
from django.utils import timezone

from bot.handlers.common import try_edit
from bot.keyboards.calendar import calendar_keyboard
from bot.keyboards.main import (
    FREQUENCY_KB,
    MAIN_MENU,
    TYPE_KB,
    confirm_keyboard,
    day_of_month_keyboard,
    remind_before_keyboard,
    weekday_keyboard,
)
from bot.keyboards.time_picker import hours_keyboard, minutes_keyboard
from bot.limits import acheck_limits
from bot.states import CreateReminder
from bot.utils import WEEKDAY_NAMES, humanize_minutes, local_now, occurrence_passed
from calendar_sync.sync import schedule_push
from core.models import MAX_REMINDER_TEXT_LENGTH, Reminder, TelegramUser

router = Router()


# ---- старт флоу ----
@router.message(F.text == "➕ Новое напоминание")
async def new_reminder(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(CreateReminder.text)
    await message.answer("✏️ О чём напомнить?\n\nНапиши текст:")


@router.message(CreateReminder.text, F.text)
async def reminder_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) > MAX_REMINDER_TEXT_LENGTH:
        await message.answer(
            f"⚠️ Слишком длинно (макс. {MAX_REMINDER_TEXT_LENGTH:,} символов). Напиши короче:"
        )
        return
    await state.update_data(text=text)
    await state.set_state(CreateReminder.type)
    await message.answer("Какое напоминание?", reply_markup=TYPE_KB)


# ---- выбор типа ----
@router.callback_query(CreateReminder.type, F.data == "type:once")
async def type_once(callback: CallbackQuery, state: FSMContext, db_user: TelegramUser):
    data = await state.get_data()
    if "edit_id" not in data:
        ok, msg = await acheck_limits(db_user, Reminder.Kind.ONCE)
        if not ok:
            await callback.message.edit_text(msg)
            await state.clear()
            await callback.answer()
            return
    await state.update_data(kind="once")
    await state.set_state(CreateReminder.date)
    today = local_now(db_user.timezone).date()
    await callback.message.edit_text(
        "📅 Выбери дату:", reply_markup=calendar_keyboard(today.year, today.month, today)
    )
    await callback.answer()


@router.callback_query(CreateReminder.type, F.data == "type:regular")
async def type_regular(callback: CallbackQuery, state: FSMContext):
    await state.update_data(kind="regular")
    await state.set_state(CreateReminder.frequency)
    await callback.message.edit_text("🔁 Как часто напоминать?", reply_markup=FREQUENCY_KB)
    await callback.answer()


# ---- календарь ----
@router.callback_query(CreateReminder.date, F.data.startswith("cal:"))
async def calendar_cb(callback: CallbackQuery, state: FSMContext, db_user: TelegramUser):
    parts = callback.data.split(":")
    action = parts[1]
    today = local_now(db_user.timezone).date()

    if action == "noop":
        await callback.answer()
        return
    if action in ("prev", "next"):
        year, month = int(parts[2]), int(parts[3])
        if action == "prev":
            month -= 1
            if month == 0:
                month, year = 12, year - 1
        else:
            month += 1
            if month == 13:
                month, year = 1, year + 1
        await try_edit(callback.message, "📅 Выбери дату:", calendar_keyboard(year, month, today))
        await callback.answer()
        return
    if action == "pick":
        year, month, day = int(parts[2]), int(parts[3]), int(parts[4])
        await state.update_data(date=f"{year:04d}-{month:02d}-{day:02d}")
        await state.set_state(CreateReminder.hour)
        await callback.message.edit_text("🕐 Выбери час:", reply_markup=hours_keyboard())
        await callback.answer()


# ---- время ----
@router.callback_query(CreateReminder.hour, F.data.startswith("time:h:"))
async def pick_hour(callback: CallbackQuery, state: FSMContext):
    hour = int(callback.data.split(":")[2])
    await state.update_data(hour=hour)
    await state.set_state(CreateReminder.minute)
    await callback.message.edit_text("🕐 Выбери минуты:", reply_markup=minutes_keyboard())
    await callback.answer()


@router.callback_query(CreateReminder.minute, F.data == "time:back")
async def back_to_hour(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateReminder.hour)
    await callback.message.edit_text("🕐 Выбери час:", reply_markup=hours_keyboard())
    await callback.answer()


@router.callback_query(CreateReminder.minute, F.data.startswith("time:m:"))
async def pick_minute(callback: CallbackQuery, state: FSMContext, db_user: TelegramUser):
    minute = int(callback.data.split(":")[2])
    await state.update_data(minute=minute)
    await state.set_state(CreateReminder.remind_before)
    await callback.message.edit_text(
        "⏰ Напомнить заранее? Первое напоминание придёт за выбранное время до, "
        "второе — в сам момент.",
        reply_markup=remind_before_keyboard("rb:pick", db_user.default_remind_before, "back:minute"),
    )
    await callback.answer()


# ---- предупреждение заранее (интервал) ----
@router.callback_query(CreateReminder.remind_before, F.data.startswith("rb:pick:"))
async def pick_remind_before(callback: CallbackQuery, state: FSMContext, db_user: TelegramUser):
    val = callback.data.split(":")[2]
    remind_before = None if val == "default" else int(val)
    await state.update_data(remind_before=remind_before)
    await _show_confirm(callback, state, db_user)
    await callback.answer()


@router.callback_query(CreateReminder.remind_before, F.data == "back:minute")
async def rb_back_to_minute(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateReminder.minute)
    await callback.message.edit_text("🕐 Выбери минуты:", reply_markup=minutes_keyboard())
    await callback.answer()


async def _show_confirm(callback: CallbackQuery, state: FSMContext, db_user: TelegramUser):
    data = await state.get_data()
    await state.set_state(CreateReminder.confirm)
    await callback.message.edit_text(
        f"📝 Проверь напоминание:\n\n{_summary(data, db_user)}", reply_markup=confirm_keyboard()
    )


# ---- частота ----
@router.callback_query(CreateReminder.frequency, F.data == "back:type")
async def back_to_type(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateReminder.type)
    await callback.message.edit_text("Какое напоминание?", reply_markup=TYPE_KB)
    await callback.answer()


@router.callback_query(F.data == "back:freq")
async def back_to_freq(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateReminder.frequency)
    await callback.message.edit_text("🔁 Как часто напоминать?", reply_markup=FREQUENCY_KB)
    await callback.answer()


@router.callback_query(CreateReminder.frequency, F.data.startswith("freq:"))
async def pick_freq(callback: CallbackQuery, state: FSMContext, db_user: TelegramUser):
    freq = callback.data.split(":")[1]
    data = await state.get_data()
    if "edit_id" not in data:
        ok, msg = await acheck_limits(db_user, freq)
        if not ok:
            await callback.message.edit_text(msg)
            await state.clear()
            await callback.answer()
            return
    await state.update_data(freq=freq)
    if freq == "weekly":
        await state.update_data(weekdays=[])
        await state.set_state(CreateReminder.weekday)
        await callback.message.edit_text(
            "📆 Выбери дни недели (можно несколько):", reply_markup=weekday_keyboard()
        )
    elif freq == "monthly":
        await state.set_state(CreateReminder.day_of_month)
        await callback.message.edit_text("🗓 Выбери число месяца:", reply_markup=day_of_month_keyboard())
    else:
        await state.set_state(CreateReminder.hour)
        await callback.message.edit_text("🕐 Выбери час:", reply_markup=hours_keyboard())
    await callback.answer()


@router.callback_query(CreateReminder.weekday, F.data.startswith("wd:toggle:"))
async def toggle_weekday(callback: CallbackQuery, state: FSMContext):
    day = int(callback.data.split(":")[2])
    data = await state.get_data()
    selected = set(data.get("weekdays", []))
    if day in selected:
        selected.discard(day)
    else:
        selected.add(day)
    await state.update_data(weekdays=sorted(selected))
    await callback.message.edit_text(
        "📆 Выбери дни недели (можно несколько):", reply_markup=weekday_keyboard(selected)
    )
    await callback.answer()


@router.callback_query(CreateReminder.weekday, F.data == "wd:done")
async def weekday_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("weekdays"):
        await callback.answer("Выбери хотя бы один день", show_alert=True)
        return
    await state.set_state(CreateReminder.hour)
    await callback.message.edit_text("🕐 Выбери час:", reply_markup=hours_keyboard())
    await callback.answer()


@router.callback_query(CreateReminder.day_of_month, F.data.startswith("dom:"))
async def pick_dom(callback: CallbackQuery, state: FSMContext):
    dom = int(callback.data.split(":")[1])
    await state.update_data(day_of_month=dom)
    await state.set_state(CreateReminder.hour)
    await callback.message.edit_text("🕐 Выбери час:", reply_markup=hours_keyboard())
    await callback.answer()


# ---- подтверждение ----
@router.callback_query(CreateReminder.confirm, F.data == "confirm:yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext, db_user: TelegramUser):
    data = await state.get_data()
    is_edit = "edit_id" in data
    if is_edit:
        await _update_reminder(data["edit_id"], data)
        pk = data["edit_id"]
    else:
        pk = await _create_reminder(db_user.pk, data)
    await state.clear()
    await schedule_push(pk)
    await callback.message.edit_text(
        "✅ Готово! Напоминание обновлено." if is_edit else "✅ Готово! Напоминание создано."
    )
    await callback.message.answer("Что дальше?", reply_markup=MAIN_MENU)
    await callback.answer()


@router.callback_query(CreateReminder.confirm, F.data == "confirm:no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.message.answer("Что дальше?", reply_markup=MAIN_MENU)
    await callback.answer()


# ---- отмена (глобально) ----
@router.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await try_edit(callback.message, "❌ Отменено.")
    await callback.message.answer("Что дальше?", reply_markup=MAIN_MENU)
    await callback.answer()


# ---- helpers ----
def _summary(data: dict, db_user: TelegramUser | None = None) -> str:
    text = escape(data.get("text", ""))
    rb = data.get("remind_before")
    rb_label = "по умолчанию" if rb is None else humanize_minutes(rb)
    if data.get("kind") == "once":
        h, m = data.get("hour", 0), data.get("minute", 0)
        return f"⏰ {data.get('date')} в {h:02d}:{m:02d}\n⏳ Предупредить: {rb_label}\n📝 {text}"
    freq = data.get("freq")
    h, m = data.get("hour", 0), data.get("minute", 0)
    if freq == "daily":
        sched = f"🔁 Ежедневно в {h:02d}:{m:02d}"
    elif freq == "weekly":
        days = ", ".join(WEEKDAY_NAMES[d] for d in sorted(data.get("weekdays", [])))
        sched = f"🔁 Еженедельно ({days}) в {h:02d}:{m:02d}"
    else:
        sched = f"🔁 Ежемесячно ({data.get('day_of_month')}-го) в {h:02d}:{m:02d}"
    return f"{sched}\n⏳ Предупредить: {rb_label}\n📝 {text}"


@sync_to_async
def _update_reminder(pk: int, data: dict):
    """Обновляет расписание напоминания (при редактировании)."""
    r = Reminder.objects.select_related("user").get(pk=pk)
    hour = data.get("hour", 0)
    minute = data.get("minute", 0)
    r.remind_before = data.get("remind_before")

    if data.get("kind") == "once":
        local = datetime.strptime(f"{data['date']} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")
        aware = local.replace(tzinfo=ZoneInfo(r.user.timezone or "UTC"))
        r.kind = Reminder.Kind.ONCE
        r.remind_at = aware.astimezone(dt_timezone.utc)
        r.time = None
        r.weekdays = []
        r.day_of_month = None
        r.last_sent_at = None
        r.pre_sent_at = None
    else:
        r.kind = data["freq"]
        r.time = dt_time(hour=hour, minute=minute)
        r.remind_at = None
        r.weekdays = data.get("weekdays")
        r.day_of_month = data.get("day_of_month")
        skip = occurrence_passed(r.kind, r.time, r.weekdays, r.day_of_month, r.user.timezone)
        r.last_sent_at = timezone.now() if skip else None
        r.pre_sent_at = None

    r.is_active = True
    r.save()


@sync_to_async
def _create_reminder(user_pk: int, data: dict):
    user = TelegramUser.objects.get(pk=user_pk)
    text = data["text"]
    hour = data.get("hour", 0)
    minute = data.get("minute", 0)
    remind_before = data.get("remind_before")

    if data.get("kind") == "once":
        local = datetime.strptime(f"{data['date']} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")
        aware = local.replace(tzinfo=ZoneInfo(user.timezone or "UTC"))
        r = Reminder.objects.create(
            user=user, text=text, kind=Reminder.Kind.ONCE,
            remind_at=aware.astimezone(dt_timezone.utc),
            remind_before=remind_before,
        )
        return r.pk

    t = dt_time(hour=hour, minute=minute)
    freq = data["freq"]
    weekdays = data.get("weekdays", []) if freq == "weekly" else None
    dom = data.get("day_of_month") if freq == "monthly" else None
    skip_today = occurrence_passed(freq, t, weekdays, dom, user.timezone)
    last_sent = timezone.now() if skip_today else None

    if freq == "weekly":
        r = Reminder.objects.create(
            user=user, text=text, kind=Reminder.Kind.WEEKLY, time=t,
            weekdays=weekdays, last_sent_at=last_sent, remind_before=remind_before,
        )
    elif freq == "monthly":
        r = Reminder.objects.create(
            user=user, text=text, kind=Reminder.Kind.MONTHLY, time=t,
            day_of_month=dom, last_sent_at=last_sent, remind_before=remind_before,
        )
    else:
        r = Reminder.objects.create(
            user=user, text=text, kind=Reminder.Kind.DAILY, time=t,
            last_sent_at=last_sent, remind_before=remind_before,
        )
    return r.pk
