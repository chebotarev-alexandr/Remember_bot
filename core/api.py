"""HTTP API для внешних потребителей (e-ink панель и т.п.).

Публичный JSON без DRF: /api/my-events/?token=... отдаёт активные напоминания
владельца (PLANNER_OWNER_TELEGRAM_ID) — для экрана «Сегодня» на панели.
"""

from django.conf import settings
from django.http import JsonResponse

from .models import Reminder, TelegramUser


def my_events(request):
    token = request.GET.get("token", "") or request.headers.get("X-Api-Token", "")
    if not settings.PLANNER_API_TOKEN or token != settings.PLANNER_API_TOKEN:
        return JsonResponse({"error": "unauthorized"}, status=401)

    user = TelegramUser.objects.filter(telegram_id=settings.PLANNER_OWNER_TELEGRAM_ID).first()
    if user is None:
        return JsonResponse({"timezone": "UTC", "count": 0, "events": []})

    events = []
    qs = Reminder.objects.filter(user=user, is_active=True, is_deleted=False)
    for r in qs:
        events.append({
            "id": r.pk,
            "text": r.text,
            "kind": r.kind,
            "remind_at": r.remind_at.isoformat() if r.remind_at else None,
            "time": r.time.strftime("%H:%M") if r.time else None,
            "weekdays": r.weekdays or [],
            "day_of_month": r.day_of_month,
        })

    return JsonResponse({
        "timezone": user.timezone or "UTC",
        "count": len(events),
        "events": events,
    })
