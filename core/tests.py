"""Тесты: лимиты тарифов, логика due-check, конвертация часовых поясов."""

from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from bot.limits import check_limits
from bot.scheduler import build_body, is_due, is_pre_due
from bot.utils import extract_links, humanize_minutes
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

    def test_deleted_not_counted(self):
        for _ in range(10):
            self._make(Reminder.Kind.DAILY, is_deleted=True)
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

    def test_deleted_reminder_not_due(self):
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.DAILY, time=time(0, 0),
        )
        r.is_deleted = True
        r.save()
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


class MyEventsApiTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(
            telegram_id=401678632, timezone="Asia/Vladivostok", first_name="Александр"
        )
        other = TelegramUser.objects.create(telegram_id=999, timezone="UTC")
        Reminder.objects.create(user=self.user, text="Вокал", kind=Reminder.Kind.WEEKLY, time=time(20, 30), weekdays=[2])
        Reminder.objects.create(user=self.user, text="Купить чай", kind=Reminder.Kind.ONCE,
                                remind_at=timezone.now() + timedelta(days=1))
        Reminder.objects.create(user=other, text="Чужое", kind=Reminder.Kind.DAILY, time=time(9, 0))

    def test_requires_token(self):
        resp = self.client.get("/api/my-events/")
        self.assertEqual(resp.status_code, 401)

    def test_returns_only_owner_events(self):
        with self.settings(PLANNER_API_TOKEN="tok"):
            resp = self.client.get("/api/my-events/", {"token": "tok"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["timezone"], "Asia/Vladivostok")
        texts = {e["text"] for e in data["events"]}
        self.assertEqual(texts, {"Вокал", "Купить чай"})

    def test_bad_token_401(self):
        with self.settings(PLANNER_API_TOKEN="tok"):
            resp = self.client.get("/api/my-events/", {"token": "wrong"})
        self.assertEqual(resp.status_code, 401)


class PreDueTests(TestCase):
    """Предупреждение заранее (первое напоминание за N минут до)."""

    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=1, timezone="UTC")

    def _once(self, remind_at, **kw):
        return Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.ONCE, remind_at=remind_at, **kw
        )

    def _daily(self, t, **kw):
        return Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.DAILY, time=t, **kw
        )

    # ---- однократное ----
    def test_once_within_window(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=dt_timezone.utc)
        self.assertTrue(is_pre_due(self._once(now + timedelta(minutes=10)), now, 15))

    def test_once_before_window(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=dt_timezone.utc)
        self.assertFalse(is_pre_due(self._once(now + timedelta(minutes=30)), now, 15))

    def test_once_at_or_past_time_not_pre_due(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=dt_timezone.utc)
        self.assertFalse(is_pre_due(self._once(now - timedelta(minutes=1)), now, 15))

    def test_once_already_pre_sent(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=dt_timezone.utc)
        r = self._once(now + timedelta(minutes=10), pre_sent_at=now - timedelta(minutes=1))
        self.assertFalse(is_pre_due(r, now, 15))

    # ---- ежедневное ----
    def test_daily_within_window(self):
        now = datetime(2026, 10, 20, 9, 5, tzinfo=dt_timezone.utc)
        self.assertTrue(is_pre_due(self._daily(time(9, 15)), now, 15))

    def test_daily_before_window(self):
        now = datetime(2026, 10, 20, 8, 50, tzinfo=dt_timezone.utc)
        self.assertFalse(is_pre_due(self._daily(time(9, 15)), now, 15))

    def test_daily_after_time_not_pre_due(self):
        # бот «догнал» после момента — предупреждение пропускается, остаётся основное
        now = datetime(2026, 10, 20, 9, 30, tzinfo=dt_timezone.utc)
        self.assertFalse(is_pre_due(self._daily(time(9, 15)), now, 15))

    def test_daily_already_pre_sent_same_day(self):
        now = datetime(2026, 10, 20, 9, 5, tzinfo=dt_timezone.utc)
        r = self._daily(time(9, 15), pre_sent_at=now - timedelta(minutes=1))
        self.assertFalse(is_pre_due(r, now, 15))

    # ---- еженедельное / ежемесячное ----
    def test_weekly_relevant_day(self):
        now = datetime(2026, 10, 20, 9, 5, tzinfo=dt_timezone.utc)
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.WEEKLY,
            time=time(9, 15), weekdays=[now.weekday()],
        )
        self.assertTrue(is_pre_due(r, now, 15))

    def test_weekly_other_day(self):
        now = datetime(2026, 10, 20, 9, 5, tzinfo=dt_timezone.utc)
        other = (now.weekday() + 1) % 7
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.WEEKLY,
            time=time(9, 15), weekdays=[other],
        )
        self.assertFalse(is_pre_due(r, now, 15))

    def test_monthly_on_day(self):
        now = datetime(2026, 10, 20, 9, 5, tzinfo=dt_timezone.utc)
        r = Reminder.objects.create(
            user=self.user, text="t", kind=Reminder.Kind.MONTHLY,
            time=time(9, 15), day_of_month=now.day,
        )
        self.assertTrue(is_pre_due(r, now, 15))

    # ---- отключения ----
    def test_zero_interval_disables(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=dt_timezone.utc)
        self.assertFalse(is_pre_due(self._once(now + timedelta(minutes=5)), now, 0))

    def test_inactive_not_pre_due(self):
        now = datetime(2026, 10, 20, 9, 5, tzinfo=dt_timezone.utc)
        self.assertFalse(is_pre_due(self._daily(time(9, 15), is_active=False), now, 15))

    def test_deleted_not_pre_due(self):
        now = datetime(2026, 10, 20, 9, 5, tzinfo=dt_timezone.utc)
        self.assertFalse(is_pre_due(self._daily(time(9, 15), is_deleted=True), now, 15))

    def test_blocked_user_not_pre_due(self):
        self.user.is_blocked = True
        self.user.save()
        now = datetime(2026, 10, 20, 9, 5, tzinfo=dt_timezone.utc)
        self.assertFalse(is_pre_due(self._daily(time(9, 15)), now, 15))


class EffectiveRemindBeforeTests(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(telegram_id=1, timezone="UTC", default_remind_before=15)

    def _make(self, **kw):
        return Reminder.objects.create(user=self.user, text="t", kind=Reminder.Kind.DAILY, time=time(9, 0), **kw)

    def test_per_reminder_wins(self):
        self.assertEqual(self._make(remind_before=30).effective_remind_before(), 30)

    def test_falls_back_to_user_default(self):
        self.assertEqual(self._make().effective_remind_before(), 15)

    def test_user_default_changed(self):
        self.user.default_remind_before = 60
        self.user.save()
        self.assertEqual(self._make().effective_remind_before(), 60)

    def test_default_is_15(self):
        user2 = TelegramUser.objects.create(telegram_id=2, timezone="UTC")
        r = Reminder.objects.create(user=user2, text="t", kind=Reminder.Kind.DAILY, time=time(9, 0))
        self.assertEqual(r.effective_remind_before(), 15)


class HumanizeMinutesTests(TestCase):
    def test_humanize(self):
        self.assertEqual(humanize_minutes(0), "не напоминать заранее")
        self.assertEqual(humanize_minutes(None), "не напоминать заранее")
        self.assertEqual(humanize_minutes(5), "5 мин")
        self.assertEqual(humanize_minutes(15), "15 мин")
        self.assertEqual(humanize_minutes(60), "1 час")
        self.assertEqual(humanize_minutes(90), "1 ч 30 мин")
        self.assertEqual(humanize_minutes(120), "2 ч")
        self.assertEqual(humanize_minutes(1440), "1 день")


class ExtractLinksTests(TestCase):
    def test_no_links(self):
        self.assertEqual(extract_links("просто текст без ссылок"), [])

    def test_single_link(self):
        self.assertEqual(extract_links("Созвон: https://zoom.us/j/123456"), ["https://zoom.us/j/123456"])

    def test_multiple_links(self):
        text = "https://meet.google.com/abc и https://t.me/joinchat/xyz"
        self.assertEqual(extract_links(text), ["https://meet.google.com/abc", "https://t.me/joinchat/xyz"])

    def test_max_three(self):
        text = "a https://a.com b https://b.com c https://c.com d https://d.com"
        self.assertEqual(extract_links(text), ["https://a.com", "https://b.com", "https://c.com"])

    def test_strips_trailing_punctuation(self):
        self.assertEqual(extract_links("Ссылка: (https://zoom.us/j/1)."), ["https://zoom.us/j/1"])

    def test_balanced_parens_kept(self):
        # скобки сбалансированы — оставляем как есть (часть URL)
        self.assertEqual(extract_links("https://a.com/x(y)"), ["https://a.com/x(y)"])

    def test_dedupe(self):
        self.assertEqual(extract_links("https://a.com и ещё https://a.com"), ["https://a.com"])

    def test_empty(self):
        self.assertEqual(extract_links(""), [])


class BuildBodyTests(TestCase):
    def test_title_only(self):
        self.assertEqual(build_body("Заголовок", ""), "<b>Заголовок</b>")

    def test_title_and_description(self):
        body = build_body("Заголовок", "Описание встречи")
        self.assertIn("<b>Заголовок</b>", body)
        self.assertIn("Описание встречи", body)

    def test_escapes_html(self):
        body = build_body("Заголовок <script>", "Описание & ссылка")
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)
