"""Движок двусторонней синхронизации «бот ↔ календари»."""

import asyncio
import logging
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.utils import timezone

from core.models import Reminder

from .convert import apply_event, reminder_to_event
from .models import CalendarConnection, ReminderEventLink
from .providers import get_provider

logger = logging.getLogger(__name__)

LOOKBACK = timedelta(days=1)
LOOKAHEAD = timedelta(days=400)


def _finalize_schedule(reminder: Reminder) -> None:
    """Пропускает текущее вхождение, если его время уже прошло (для регулярных)."""
    from bot.utils import occurrence_passed

    if reminder.kind != Reminder.Kind.ONCE:
        skip = occurrence_passed(
            reminder.kind,
            reminder.time,
            reminder.weekdays,
            reminder.day_of_month,
            reminder.user.timezone,
        )
        reminder.last_sent_at = timezone.now() if skip else None


# ----------------------------- Bot -> Calendar -----------------------------

def push_reminder(reminder_id: int) -> None:
    """Синхронизирует напоминание во все активные календари пользователя."""
    reminder = Reminder.objects.select_related("user").get(pk=reminder_id)
    for connection in reminder.user.calendar_connections.filter(is_active=True):
        try:
            _push_to_connection(connection, reminder)
        except Exception:
            logger.exception("Ошибка push в календарь %s для напоминания %s", connection.provider, reminder_id)


def _push_to_connection(connection: CalendarConnection, reminder: Reminder) -> None:
    provider = get_provider(connection)
    link = connection.event_links.filter(reminder=reminder).first()

    if reminder.is_deleted:
        if link:
            provider.delete_event(link.external_event_id)
            link.delete()
        return

    event = reminder_to_event(reminder)
    if link:
        provider.update_event(link.external_event_id, event)
    else:
        external_id = provider.create_event(event)
        ReminderEventLink.objects.create(
            reminder=reminder, connection=connection, external_event_id=external_id
        )


async def schedule_push(reminder_id: int) -> None:
    """Fire-and-forget отправка напоминания в календари из async-обработчика."""
    asyncio.create_task(_push_task(reminder_id))


async def _push_task(reminder_id: int) -> None:
    try:
        await sync_to_async(push_reminder)(reminder_id)
    except Exception:
        logger.exception("Ошибка push напоминания %s", reminder_id)


# ----------------------------- Calendar -> Bot -----------------------------

def pull_connection(connection_id: int) -> int:
    """Тянет события из календаря в бота. Возвращает число изменений."""
    connection = CalendarConnection.objects.select_related("user").get(pk=connection_id)
    provider = get_provider(connection)
    now = timezone.now()
    events = provider.list_events(now - LOOKBACK, now + LOOKAHEAD)
    event_map = {e["id"]: e for e in events}

    changes = 0
    known_ids: set[str] = set()

    for link in connection.event_links.select_related("reminder"):
        event = event_map.get(link.external_event_id)
        if event is None:
            # Событие удалено в календаре — помечаем напоминание удалённым
            link.reminder.is_deleted = True
            link.reminder.save(update_fields=["is_deleted"])
            link.delete()
            changes += 1
            continue
        known_ids.add(link.external_event_id)
        reminder = link.reminder
        apply_event(reminder, event)
        _finalize_schedule(reminder)
        reminder.save()
        changes += 1

    for event_id, event in event_map.items():
        if event_id in known_ids:
            continue
        # Однократные события в прошлом не превращаем в напоминания
        if not event.get("rrule") and event["start"] < now:
            continue
        reminder = Reminder(user=connection.user, text="", kind=Reminder.Kind.ONCE)
        apply_event(reminder, event)
        _finalize_schedule(reminder)
        reminder.save()
        ReminderEventLink.objects.create(
            reminder=reminder, connection=connection, external_event_id=event_id
        )
        changes += 1

    connection.last_synced_at = timezone.now()
    connection.save(update_fields=["last_synced_at"])
    return changes


@sync_to_async
def _pull_all() -> int:
    total = 0
    for connection in CalendarConnection.objects.filter(is_active=True):
        try:
            total += pull_connection(connection.pk)
        except Exception:
            logger.exception("Ошибка pull для подключения %s", connection.pk)
    return total
