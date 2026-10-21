"""Тесты синхронизации календарей."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.test import TestCase

from calendar_sync.convert import apply_event, reminder_to_event
from core.models import Reminder, TelegramUser


class ConvertTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=1, timezone="Europe/Moscow")

    def test_daily_reminder_to_event(self):
        r = Reminder.objects.create(
            user=self.user, text="тест", kind=Reminder.Kind.DAILY, time=time(9, 0),
        )
        ev = reminder_to_event(r)
        self.assertEqual(ev["summary"], "тест")
        self.assertEqual(ev["rrule"], "FREQ=DAILY")
        self.assertEqual(ev["start"].time(), time(9, 0))

    def test_weekly_reminder_to_event(self):
        r = Reminder.objects.create(
            user=self.user, text="тест", kind=Reminder.Kind.WEEKLY, time=time(14, 25),
            weekdays=[1, 2, 5],
        )
        ev = reminder_to_event(r)
        self.assertEqual(ev["rrule"], "FREQ=WEEKLY;BYDAY=TU,WE,SA")

    def test_monthly_reminder_to_event(self):
        r = Reminder.objects.create(
            user=self.user, text="тест", kind=Reminder.Kind.MONTHLY, time=time(10, 0),
            day_of_month=15,
        )
        ev = reminder_to_event(r)
        self.assertEqual(ev["rrule"], "FREQ=MONTHLY;BYMONTHDAY=15")

    def test_apply_once_event(self):
        start = datetime(2026, 10, 22, 14, 30, tzinfo=ZoneInfo("Europe/Moscow"))
        r = Reminder(user=self.user, text="", kind=Reminder.Kind.ONCE)
        apply_event(r, {"id": "x", "summary": "событие", "start": start, "rrule": None})
        self.assertEqual(r.kind, Reminder.Kind.ONCE)
        self.assertEqual(r.text, "событие")
        self.assertIsNotNone(r.remind_at)

    def test_apply_weekly_event(self):
        start = datetime(2026, 10, 21, 14, 25, tzinfo=ZoneInfo("Europe/Moscow"))
        r = Reminder(user=self.user, text="", kind=Reminder.Kind.ONCE)
        apply_event(
            r, {"id": "x", "summary": "вокал", "start": start, "rrule": "FREQ=WEEKLY;BYDAY=TU,WE,SA"}
        )
        self.assertEqual(r.kind, Reminder.Kind.WEEKLY)
        self.assertEqual(sorted(r.weekdays), [1, 2, 5])
        self.assertEqual(r.time, time(14, 25))

    def test_apply_daily_event(self):
        start = datetime(2026, 10, 21, 20, 30, tzinfo=ZoneInfo("Europe/Moscow"))
        r = Reminder(user=self.user, text="", kind=Reminder.Kind.ONCE)
        apply_event(r, {"id": "x", "summary": "вокал", "start": start, "rrule": "FREQ=DAILY"})
        self.assertEqual(r.kind, Reminder.Kind.DAILY)
        self.assertEqual(r.time, time(20, 30))
