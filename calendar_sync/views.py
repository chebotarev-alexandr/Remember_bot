"""OAuth-колбэки (после авторизации пользователя в вебе)."""

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from . import oauth
from .models import CalendarConnection, PendingOAuth
from .providers.google import GoogleCalendarProvider
from .providers.yandex import YandexCalendarProvider

_SUCCESS = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Подключено</title></head><body style="font-family:sans-serif;text-align:center;padding-top:80px">
<h2>✅ {msg}</h2><p>Можно вернуться в Telegram.</p></body></html>"""

_ERROR = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Ошибка</title></head><body style="font-family:sans-serif;text-align:center;padding-top:80px">
<h2>⚠️ {msg}</h2><p>Вернись в бот и попробуй подключиться заново.</p></body></html>"""


@csrf_exempt
def google_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    pending = PendingOAuth.objects.filter(state=state, provider="google").first()
    if not pending:
        return HttpResponse(_ERROR.format(msg="Неверное состояние OAuth."), status=400)
    if not code:
        return HttpResponse(_ERROR.format(msg="Нет кода авторизации."), status=400)
    try:
        token = oauth.exchange_google_code(code, pending.code_verifier)
    except Exception:
        return HttpResponse(_ERROR.format(msg="Не удалось обменять код."), status=400)
    user = pending.user
    pending.delete()
    try:
        conn, _ = CalendarConnection.objects.update_or_create(
            user=user, provider="google", defaults={"credentials": token, "is_active": True}
        )
        cal_id = GoogleCalendarProvider(conn).validate()
        conn.calendar_id = cal_id or "primary"
        conn.save(update_fields=["calendar_id"])
    except Exception:
        return HttpResponse(_ERROR.format(msg="Токен получен, но календарь не проверился."), status=400)
    return HttpResponse(_SUCCESS.format(msg="Google Calendar подключён!"))


@csrf_exempt
def yandex_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")
    pending = PendingOAuth.objects.filter(state=state, provider="yandex").first()
    if not pending:
        return HttpResponse(_ERROR.format(msg="Неверное состояние OAuth."), status=400)
    if not code:
        return HttpResponse(_ERROR.format(msg="Нет кода авторизации."), status=400)
    try:
        token = oauth.exchange_yandex_code(code)
    except Exception:
        return HttpResponse(_ERROR.format(msg="Не удалось обменять код."), status=400)
    user = pending.user
    pending.delete()
    try:
        conn, _ = CalendarConnection.objects.update_or_create(
            user=user, provider="yandex", defaults={"credentials": token, "is_active": True}
        )
        cal_id = YandexCalendarProvider(conn).validate()
        conn.calendar_id = cal_id
        conn.save(update_fields=["calendar_id"])
    except Exception:
        return HttpResponse(_ERROR.format(msg="Токен получен, но календарь не проверился."), status=400)
    return HttpResponse(_SUCCESS.format(msg="Яндекс Календарь подключён!"))
