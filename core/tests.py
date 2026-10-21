"""Тесты: лимиты тарифов, логика due-check, конвертация часовых поясов."""

from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from bot.limits import check_limits
from bot.scheduler import is_due
from core.models import Reminder, TelegramUser


class LimitsTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=1, timezone="Europe/Moscow")

    def _make(self, kind, **kw):
        defaults = {"user": self.user, "text": "тест", "kind": kind}
        if kind == Reminder.Kind.ONCE:
            defaults["remind_at"] = timezone.now() + timedelta(hours=1)
        else:
            defaults["time"] = time(9, 0)
        defaults.update(kw)
        return Reminder.objects.create(**defaults)

    def test_free_regular_limit(self):
        for _ in range(10):
            self._make(Reminder.Kind.DAILY)
        ok, msg = check_limits(self.user, Reminder.Kind.DAILY)
        self.assertFalse(ok)
        self.assertIn("10", msg)

    def test_free_once_limit(self):
        for _ in range(3):
            self._make(Reminder.Kind.ONCE)
        ok, msg = check_limits(self.user, Reminder.Kind.ONCE)
        self.assertFalse(ok)
        self.assertIn("3", msg)

    def test_under_limit_ok(self):
        self._make(Reminder.Kind.DAILY)
        ok, _ = check_limits(self.user, Reminder.Kind.DAILY)
        self.assertTrue(ok)

    def test_premium_unlimited(self):
        self.user.is_premium = True
        self.user.save()
        for _ in range(50):
            self._make(Reminder.Kind.DAILY)
        ok, _ = check_limits(self.user, Reminder.Kind.DAILY)
        self.assertTrue(ok)


class DueCheckTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=1, timezone="Europe/Moscow")

    def test_once_due_in_past(self):
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.ONCE,
            remind_at=timezone.now() - timedelta(minutes=5),
        )
        self.assertTrue(is_due(r, timezone.now()))

    def test_once_not_due_in_future(self):
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.ONCE,
            remind_at=timezone.now() + timedelta(hours=2),
        )
        self.assertFalse(is_due(r, timezone.now()))

    def test_daily_due_after_time(self):
        r = Reminder.objects.create(user=self.user, text="t", kind=Reminder.Kind.DAILY, time=time(0, 0))
        self.assertTrue(is_due(r, timezone.now()))

    def test_daily_not_due_if_already_sent(self):
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.DAILY, time=time(0, 0),
            last_sent_at=timezone.now(),
        )
        self.assertFalse(is_due(r, timezone.now()))

    def test_weekly_due_on_chosen_day(self):
        local_now = timezone.now().astimezone(ZoneInfo("Europe/Moscow"))
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.WEEKLY, time=time(0, 0),
            weekdays=[local_now.weekday()],
        )
        self.assertTrue(is_due(r, timezone.now()))

    def test_weekly_not_due_other_day(self):
        local_now = timezone.now().astimezone(ZoneInfo("Europe/Moscow"))
        other = (local_now.weekday() + 1) % 7
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.WEEKLY, time=time(0, 0), weekdays=[other],
        )
        self.assertFalse(is_due(r, timezone.now()))

    def test_blocked_user_never_due(self):
        self.user.is_blocked = True
        self.user.save()
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.ONCE,
            remind_at=timezone.now() - timedelta(minutes=5),
        )
        self.assertFalse(is_due(r, timezone.now()))


class TimezoneTests(TestCase):
    def test_local_to_utc_conversion(self):
        # 15:00 в Москве (UTC+3) = 12:00 UTC
        local = datetime(2026, 10, 20, 15, 0).replace(tzinfo=ZoneInfo("Europe/Moscow"))
        utc = local.astimezone(dt_timezone.utc)
        self.assertEqual(utc.hour, 12)
        self.assertEqual(utc.day, 20)

    def test_vladivostok_offset(self):
        # 09:00 во Владивостоке (UTC+10) = 23:00 предыдущего дня UTC
        local = datetime(2026, 10, 20, 9, 0).replace(tzinfo=ZoneInfo("Asia/Vladivostok"))
        utc = local.astimezone(dt_timezone.utc)
        self.assertEqual(utc.hour, 23)
        self.assertEqual(utc.day, 19)


class OccurrenceTests(TestCase):
    def test_occurrence_passed(self):
        from bot import utils

        # фиксируем «сейчас»: среда 20:50 по Москве
        fixed = datetime(2026, 10, 21, 20, 50, tzinfo=ZoneInfo("Europe/Moscow"))
        with patch.object(utils, "local_now", return_value=fixed):
            # ежедневное в 20:30 — уже прошло
            self.assertTrue(utils.occurrence_passed("daily", time(20, 30), None, None, "Europe/Moscow"))
            # ежедневное в 21:00 — ещё не наступило
            self.assertFalse(utils.occurrence_passed("daily", time(21, 0), None, None, "Europe/Moscow"))
            # еженедельное в 14:25, сегодня выбранный день — прошло
            self.assertTrue(utils.occurrence_passed("weekly", time(14, 25), [fixed.weekday()], None, "Europe/Moscow"))
            # еженедельное в 14:25, завтра — не прошло
            other = (fixed.weekday() + 1) % 7
            self.assertFalse(utils.occurrence_passed("weekly", time(14, 25), [other], None, "Europe/Moscow"))
