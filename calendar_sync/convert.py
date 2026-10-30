"""Преобразование «напоминание ↔ событие календаря».

Нормализованное событие — dict:
    {id, summary, start (aware datetime), rrule (str | None)}
"""

import calendar as _calendar
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings

from core.models import Reminder

WEEKDAY_TO_RFC = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
RFC_TO_WEEKDAY = {v: i for i, v in enumerate(WEEKDAY_TO_RFC)}

DEFAULT_DURATION_MINUTES = int(getattr(settings, "CALENDAR_EVENT_DURATION_MINUTES", 30))


def _next_weekday(local_date: datetime, weekday: int) -> datetime:
    days_ahead = (weekday - local_date.weekday()) % 7
    return local_date + timedelta(days=days_ahead)


def _next_month_day(local_date: datetime, day_of_month: int) -> datetime:
    year, month = local_date.year, local_date.month
    last = _calendar.monthrange(year, month)[1]
    day = min(day_of_month, last)
    candidate = local_date.replace(day=day)
    if candidate.date() < local_date.date():
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
        last = _calendar.monthrange(year, month)[1]
        day = min(day_of_month, last)
        candidate = candidate.replace(year=year, month=month, day=day)
    return candidate


def reminder_to_event(reminder: Reminder) -> dict:
    """Строит нормализованное событие календаря из напоминания."""
    tz = ZoneInfo(reminder.user.timezone or "UTC")
    summary = reminder.text

    if reminder.kind == Reminder.Kind.ONCE:
        start = reminder.remind_at.astimezone(tz)
        rrule = None
    else:
        now = datetime.now(tz)
        t = reminder.time
        if reminder.kind == Reminder.Kind.DAILY:
            start = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            if start < now:
                start += timedelta(days=1)
            rrule = "FREQ=DAILY"
        elif reminder.kind == Reminder.Kind.WEEKLY:
            weekdays = sorted(reminder.weekdays or [])
            byday = ",".join(WEEKDAY_TO_RFC[d] for d in weekdays)
            first_wd = weekdays[0] if weekdays else 0
            start_date = _next_weekday(now, first_wd)
            start = start_date.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            rrule = f"FREQ=WEEKLY;BYDAY={byday}"
        else:  # MONTHLY
            dom = reminder.day_of_month or 1
            start_date = _next_month_day(now, dom)
            start = start_date.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            rrule = f"FREQ=MONTHLY;BYMONTHDAY={dom}"

    end = start + timedelta(minutes=DEFAULT_DURATION_MINUTES)
    return {
        "summary": summary,
        "description": reminder.description or "",
        "start": start,
        "end": end,
        "rrule": rrule,
        "timezone": str(tz),
    }


def apply_event(reminder: Reminder, event: dict) -> None:
    """Применяет нормализованное событие календаря к напоминанию (mutate, без save)."""
    tz = ZoneInfo(reminder.user.timezone or "UTC")
    start = event["start"].astimezone(tz)
    rrule = (event.get("rrule") or "").upper()

    reminder.text = event["summary"]
    reminder.description = event.get("description") or ""

    if not rrule:
        reminder.kind = Reminder.Kind.ONCE
        reminder.remind_at = event["start"].astimezone(dt_timezone.utc)
        reminder.time = None
        reminder.weekdays = []
        reminder.day_of_month = None
        return

    parts = rrule.split(";")
    freq = next((p.split("=", 1)[-1] for p in parts if p.startswith("FREQ=")), "")

    if freq == "DAILY":
        reminder.kind = Reminder.Kind.DAILY
        reminder.weekdays = []
        reminder.day_of_month = None
    elif freq == "WEEKLY":
        byday = next((p.split("=", 1)[-1] for p in parts if p.startswith("BYDAY=")), "")
        days = [RFC_TO_WEEKDAY[d] for d in byday.split(",") if d in RFC_TO_WEEKDAY]
        reminder.kind = Reminder.Kind.WEEKLY
        reminder.weekdays = sorted(days) or [start.weekday()]
        reminder.day_of_month = None
    elif freq == "MONTHLY":
        bymonthday = next((p.split("=", 1)[-1] for p in parts if p.startswith("BYMONTHDAY=")), "")
        reminder.kind = Reminder.Kind.MONTHLY
        reminder.weekdays = []
        reminder.day_of_month = int(bymonthday) if bymonthday else start.day
    else:
        # Неподдерживаемая частота — трактуем как однократное
        reminder.kind = Reminder.Kind.ONCE
        reminder.remind_at = event["start"].astimezone(dt_timezone.utc)
        reminder.time = None
        reminder.weekdays = []
        reminder.day_of_month = None
        return

    reminder.time = start.time()
    reminder.remind_at = None
    reminder.last_sent_at = None  # сброс — сработает по новому расписанию
