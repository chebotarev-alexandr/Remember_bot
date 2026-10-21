"""Планировщик напоминаний (фоновая задача в event loop)."""

import asyncio
import logging
from html import escape
from zoneinfo import ZoneInfo

from asgiref.sync import sync_to_async
from django.utils import timezone

from core.models import Reminder

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 30


def is_due(r: Reminder, now) -> bool:
    """Пора ли отправить напоминание (чистая синхронная логика, тестируемая)."""
    if not r.is_active or r.user.is_blocked:
        return False

    tz = ZoneInfo(r.user.timezone or "UTC")
    local = now.astimezone(tz)

    if r.kind == Reminder.Kind.ONCE:
        return r.remind_at is not None and r.remind_at <= now

    last_date = r.last_sent_at.astimezone(tz).date() if r.last_sent_at else None
    if r.kind == Reminder.Kind.DAILY:
        return bool(r.time and local.time() >= r.time and last_date != local.date())
    if r.kind == Reminder.Kind.WEEKLY:
        return bool(
            r.time
            and r.weekdays
            and local.weekday() in r.weekdays
            and local.time() >= r.time
            and last_date != local.date()
        )
    if r.kind == Reminder.Kind.MONTHLY:
        return bool(
            r.time
            and r.day_of_month
            and local.day == r.day_of_month
            and local.time() >= r.time
            and last_date != local.date()
        )
    return False


@sync_to_async
def _due_reminders():
    now = timezone.now()
    return [
        r
        for r in Reminder.objects.filter(is_active=True).select_related("user")
        if is_due(r, now)
    ]


@sync_to_async
def _mark_sent(pk: int):
    r = Reminder.objects.get(pk=pk)
    if r.kind == Reminder.Kind.ONCE:
        r.is_active = False
    r.last_sent_at = timezone.now()
    r.save()


async def check_due_reminders(bot) -> int:
    """Отправляет просроченные напоминания. Возвращает число отправленных."""
    due = await _due_reminders()
    for r in due:
        try:
            await bot.send_message(r.user.telegram_id, f"🔔 Напоминание:\n\n{escape(r.text)}")
        except Exception as exc:  # noqa: BLE001 — fail-silent, не роняем планировщик
            logger.warning("Ошибка отправки напоминания %s: %s", r.pk, exc)
        await _mark_sent(r.pk)
    return len(due)


async def scheduler_loop(bot):
    logger.info("Планировщик запущен (интервал %s с)", INTERVAL_SECONDS)
    while True:
        await asyncio.sleep(INTERVAL_SECONDS)
        try:
            await check_due_reminders(bot)
        except Exception:  # noqa: BLE001
            logger.exception("Ошибка в планировщике")
