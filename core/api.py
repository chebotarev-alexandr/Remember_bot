"""HTTP API для внешних потребителей (e-ink панель и т.п.).

Публичный JSON без DRF:
  /api/my-events/?token=... — активные напоминания владельца.
  /api/weather/?token=...  — погода (прокси на open-meteo; из РФ напрямую
                             open-meteo блокируется, а эта машина его видит).
"""

import json
import urllib.parse
import urllib.request

from django.conf import settings
from django.http import JsonResponse

from .models import Reminder, TelegramUser


def _authed(request) -> bool:
    token = request.GET.get("token", "") or request.headers.get("X-Api-Token", "")
    return bool(settings.PLANNER_API_TOKEN) and token == settings.PLANNER_API_TOKEN


def my_events(request):
    if not _authed(request):
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


def weather(request):
    if not _authed(request):
        return JsonResponse({"error": "unauthorized"}, status=401)

    lat = request.GET.get("lat", "48.48")
    lon = request.GET.get("lon", "135.07")
    tz = request.GET.get("tz", "Asia/Vladivostok")

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code"
        f"&timezone={urllib.parse.quote(tz)}&forecast_days=1"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "remember-bot"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return JsonResponse(data)
