"""Лимиты бесплатного тарифа."""

from asgiref.sync import sync_to_async
from django.conf import settings

from core.models import Reminder, TelegramUser


def check_limits(user: TelegramUser, kind: str) -> tuple[bool, str]:
    """Возвращает (можно_создать, сообщение_при_отказе)."""
    if user.is_premium:
        return True, ""

    if kind == Reminder.Kind.ONCE:
        count = user.reminders.filter(is_active=True, kind=Reminder.Kind.ONCE).count()
        limit = settings.FREE_ONCE_LIMIT
        label = "однократных"
    else:
        count = user.reminders.filter(is_active=True).exclude(kind=Reminder.Kind.ONCE).count()
        limit = settings.FREE_REGULAR_LIMIT
        label = "регулярных"

    if count >= limit:
        return (
            False,
            f"⚠️ Лимит бесплатного тарифа: не более {limit} {label} напоминаний "
            f"(у тебя уже {count}).\n⭐ Премиум снимает ограничения.",
        )
    return True, ""


def limits_summary(user: TelegramUser) -> str:
    """Краткая сводка лимитов для раздела «Премиум»."""
    if user.is_premium:
        return "⭐ У тебя премиум — ограничений нет."
    regular = user.reminders.filter(is_active=True).exclude(kind=Reminder.Kind.ONCE).count()
    once = user.reminders.filter(is_active=True, kind=Reminder.Kind.ONCE).count()
    return (
        f"📊 Твой тариф: бесплатный\n"
        f"• Регулярные: {regular}/{settings.FREE_REGULAR_LIMIT}\n"
        f"• Однократные: {once}/{settings.FREE_ONCE_LIMIT}"
    )


# async-обёртки для вызова из aiogram-обработчиков (ORM не работает в async-контексте)
acheck_limits = sync_to_async(check_limits)
alimits_summary = sync_to_async(limits_summary)
