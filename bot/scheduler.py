"""Планировщик напоминаний (фоновая задача в event loop).

Каждое напоминание приходит дважды:
  1) предупреждение — за N минут до (по умолчанию 15, настраивается),
  2) основное напоминание — в сам момент.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from asgiref.sync import sync_to_async
from django.utils import timezone

from bot.utils import extract_links, humanize_minutes
from core.models import Reminder

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 30
TG_MAX_MESSAGE = 4096  # лимит Telegram на одно сообщение


def is_due(r: Reminder, now) -> bool:
    """Пора ли отправить основное напоминание (чистая синхронная логика, тестируемая)."""
    if not r.is_active or r.is_deleted or r.user.is_blocked:
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


def is_pre_due(r: Reminder, now, interval_minutes: int) -> bool:
    """Пора ли отправить предупреждение (за interval_minutes до основного).

    Предупреждение уходит строго ДО основного напоминания: если бот «догнал»
    момент уже после времени срабатывания — предупреждение пропускается,
    уходит только основное.
    """
    if not r.is_active or r.is_deleted or r.user.is_blocked:
        return False
    if interval_minutes <= 0:
        return False

    interval = timedelta(minutes=interval_minutes)
    tz = ZoneInfo(r.user.timezone or "UTC")
    local = now.astimezone(tz)

    if r.kind == Reminder.Kind.ONCE:
        if r.remind_at is None:
            return False
        return r.pre_sent_at is None and r.remind_at - interval <= now < r.remind_at

    if not r.time:
        return False
    relevant = True
    if r.kind == Reminder.Kind.WEEKLY:
        relevant = bool(r.weekdays and local.weekday() in r.weekdays)
    elif r.kind == Reminder.Kind.MONTHLY:
        relevant = bool(r.day_of_month and local.day == r.day_of_month)
    if not relevant:
        return False

    pre_time = (datetime.combine(local.date(), r.time) - interval).time()
    pre_date = r.pre_sent_at.astimezone(tz).date() if r.pre_sent_at else None
    return bool(local.time() >= pre_time and local.time() < r.time and pre_date != local.date())


@sync_to_async
def _due_reminders():
    now = timezone.now()
    return [
        r
        for r in Reminder.objects.filter(is_active=True, is_deleted=False).select_related("user")
        if is_due(r, now)
    ]


@sync_to_async
def _pre_due_reminders():
    """Возвращает список (reminder, interval) для предупреждений, которые пора отправить."""
    now = timezone.now()
    out = []
    for r in Reminder.objects.filter(is_active=True, is_deleted=False).select_related("user"):
        minutes = r.effective_remind_before()
        if minutes <= 0:
            continue
        if is_pre_due(r, now, minutes):
            out.append((r, minutes))
    return out


@sync_to_async
def _mark_sent(pk: int):
    r = Reminder.objects.get(pk=pk)
    if r.kind == Reminder.Kind.ONCE:
        r.is_active = False
    r.last_sent_at = timezone.now()
    r.save()


@sync_to_async
def _mark_pre_sent(pk: int):
    Reminder.objects.filter(pk=pk).update(pre_sent_at=timezone.now())


def build_body(title: str, description: str) -> str:
    """Текст напоминания: заголовок (жирным) + описание ниже (если есть)."""
    parts = [f"<b>{escape(title)}</b>"]
    if description:
        parts.append(escape(description))
    return "\n\n".join(parts)


def links_keyboard(links: list[str]) -> InlineKeyboardMarkup | None:
    """Инлайн-кнопки для ссылок из описания (не более 3 — ограничено в extract_links)."""
    if not links:
        return None
    if len(links) == 1:
        labels = ["🔗 Открыть ссылку"]
    else:
        labels = [f"🔗 Ссылка {i + 1}" for i in range(len(links))]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, url=url)] for label, url in zip(labels, links)
        ]
    )


def _split_chunks(text: str) -> list[str]:
    return [text[i : i + TG_MAX_MESSAGE] for i in range(0, len(text), TG_MAX_MESSAGE)]


async def _send_reminder(bot, chat_id: int, title: str, description: str, prefix: str) -> None:
    """Отправляет заголовок + описание (чанками по лимиту Telegram).

    Если в описании есть ссылки — прикрепляет кнопки-ссылки к первому сообщению.
    """
    body = build_body(title, description)
    kb = links_keyboard(extract_links(description or ""))
    chunks = _split_chunks(body)
    for idx, chunk in enumerate(chunks):
        msg = f"{prefix}{chunk}" if idx == 0 else chunk
        if idx == 0 and kb is not None:
            await bot.send_message(chat_id, msg, reply_markup=kb)
        else:
            await bot.send_message(chat_id, msg)


async def _send_long_text(bot, chat_id: int, r: Reminder) -> None:
    await _send_reminder(bot, chat_id, r.text, r.description, "🔔 Напоминание:\n\n")


async def _send_pre(bot, chat_id: int, r: Reminder, minutes: int) -> None:
    await _send_reminder(bot, chat_id, r.text, r.description, f"🔔 Напомню через {humanize_minutes(minutes)}:\n\n")


async def check_due_reminders(bot) -> int:
    """Отправляет предупреждения и основные напоминания. Возвращает число отправленных."""
    sent = 0

    # 1) предупреждения (за N минут до)
    for r, minutes in await _pre_due_reminders():
        try:
            await _send_pre(bot, r.user.telegram_id, r, minutes)
        except Exception as exc:  # noqa: BLE001 — fail-silent, не роняем планировщик
            logger.warning("Ошибка отправки предупреждения %s: %s", r.pk, exc)
        await _mark_pre_sent(r.pk)
        sent += 1

    # 2) основные напоминания
    for r in await _due_reminders():
        try:
            await _send_long_text(bot, r.user.telegram_id, r)
        except Exception as exc:  # noqa: BLE001 — fail-silent
            logger.warning("Ошибка отправки напоминания %s: %s", r.pk, exc)
        await _mark_sent(r.pk)
        sent += 1

    return sent


async def scheduler_loop(bot):
    logger.info("Планировщик запущен (интервал %s с)", INTERVAL_SECONDS)
    while True:
        await asyncio.sleep(INTERVAL_SECONDS)
        try:
            await check_due_reminders(bot)
        except Exception:  # noqa: BLE001
            logger.exception("Ошибка в планировщике")


async def calendar_sync_loop():
    """Фоновая синхронизация календарей (calendar -> bot)."""
    from django.conf import settings

    from calendar_sync.sync import _pull_all

    interval = int(getattr(settings, "CALENDAR_SYNC_INTERVAL_SECONDS", 300))
    logger.info("Синхронизация календарей запущена (интервал %s с)", interval)
    while True:
        await asyncio.sleep(interval)
        try:
            await _pull_all()
        except Exception:  # noqa: BLE001
            logger.exception("Ошибка синхронизации календарей")
