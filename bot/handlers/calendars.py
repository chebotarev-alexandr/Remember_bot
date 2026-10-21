"""Подключение и синхронизация календарей (Google Calendar, Яндекс Календарь)."""

import logging
import secrets
from urllib.parse import parse_qs, urlparse

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from asgiref.sync import sync_to_async
from django.conf import settings

from bot.keyboards.main import MAIN_MENU
from bot.states import ConnectGoogle, ConnectYandex
from calendar_sync import oauth
from calendar_sync.models import CalendarConnection
from calendar_sync.providers.google import GoogleCalendarProvider
from calendar_sync.providers.yandex import YandexCalendarProvider
from calendar_sync.sync import pull_connection
from core.models import TelegramUser

logger = logging.getLogger(__name__)

router = Router()


def _parse_code(text: str):
    text = text.strip()
    if text.startswith(("http://", "https://")):
        qs = parse_qs(urlparse(text).query)
        return qs.get("code", [None])[0], qs.get("state", [None])[0]
    return text, None


def _calendars_keyboard(connections):
    rows = []
    for c in connections:
        label = f"🗑 Отключить: {c.get_provider_display()}"
        if c.calendar_name:
            label += f" ({c.calendar_name})"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"cal:disconnect:{c.pk}")])
    rows.append([InlineKeyboardButton(text="🔗 Подключить Google Calendar", callback_data="cal:connect:google")])
    rows.append([InlineKeyboardButton(text="🔗 Подключить Яндекс Календарь", callback_data="cal:connect:yandex")])
    rows.append([InlineKeyboardButton(text="🔄 Синхронизировать сейчас", callback_data="cal:sync")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@sync_to_async
def _list_connections(user_pk):
    return list(CalendarConnection.objects.filter(user_id=user_pk, is_active=True))


@sync_to_async
def _pull_user(user_pk):
    total = 0
    for conn in CalendarConnection.objects.filter(user_id=user_pk, is_active=True):
        try:
            total += pull_connection(conn.pk)
        except Exception:
            logger.exception("Ошибка pull подключения %s", conn.pk)
    return total


@router.message(F.text == "📅 Календари")
async def calendars_menu(message: Message, db_user: TelegramUser):
    connections = await _list_connections(db_user.pk)
    if connections:
        text = "📅 <b>Календари</b>\n\nПодключено:\n"
        for c in connections:
            name = c.calendar_name or "—"
            text += f"• {c.get_provider_display()}: {name}\n"
        text += "\nСобытия синхронизируются в обе стороны автоматически. Нажми на подключение, чтобы отключить."
    else:
        text = "📅 <b>Календари</b>\n\nПодключи календарь — события будут синхронизироваться в обе стороны."
    await message.answer(text, reply_markup=_calendars_keyboard(connections))


# ------------------------------- Google -------------------------------

@router.callback_query(F.data == "cal:connect:google")
async def connect_google(callback: CallbackQuery, state: FSMContext):
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        await callback.message.answer(
            "⚠️ Google OAuth не настроен на сервере.\n"
            "Нужны GOOGLE_OAUTH_CLIENT_ID и GOOGLE_OAUTH_CLIENT_SECRET в .env."
        )
        await callback.answer()
        return
    oauth_state = secrets.token_urlsafe(16)
    auth_url, verifier = oauth.build_auth_url(oauth_state)
    await state.update_data(oauth_state=oauth_state, code_verifier=verifier)
    await state.set_state(ConnectGoogle.waiting_code)
    await callback.message.answer(
        "🔗 <b>Подключение Google Calendar</b>\n\n"
        "1. Открой ссылку и разреши доступ:\n"
        f"{auth_url}\n\n"
        "2. Браузер попытается открыть localhost и покажет ошибку — это нормально.\n"
        "3. Скопируй <b>весь URL из адресной строки</b> и пришли его сюда."
    )
    await callback.answer()


@router.message(ConnectGoogle.waiting_code, F.text)
async def google_code(message: Message, state: FSMContext, db_user: TelegramUser):
    code, returned_state = _parse_code(message.text)
    data = await state.get_data()
    if not code:
        await message.answer("⚠️ Не получилось извлечь код. Пришли полный URL из адресной строки браузера.")
        return
    if returned_state and returned_state != data.get("oauth_state"):
        await message.answer("⚠️ Состояние OAuth не совпало. Попробуй подключиться заново.")
        return
    try:
        token = await sync_to_async(oauth.exchange_code)(code, data.get("code_verifier", ""))
    except Exception as exc:
        logger.warning("Ошибка обмена кода Google: %s", exc)
        await message.answer("⚠️ Не удалось получить токен. Код мог истечь — попробуй заново.")
        return
    await state.clear()
    try:
        await _connect_google(db_user.pk, token)
    except Exception as exc:
        logger.warning("Ошибка проверки Google: %s", exc)
        await message.answer("⚠️ Токен получен, но календарь не проверился. Проверь доступ и повтори.")
        return
    await message.answer("✅ Google Calendar подключён!", reply_markup=MAIN_MENU)


@sync_to_async
def _connect_google(user_pk, token):
    user = TelegramUser.objects.get(pk=user_pk)
    conn, _ = CalendarConnection.objects.update_or_create(
        user=user,
        provider="google",
        defaults={"credentials": token, "is_active": True},
    )
    cal_id = GoogleCalendarProvider(conn).validate()
    conn.calendar_id = cal_id or "primary"
    conn.save(update_fields=["calendar_id"])
    return conn


# ------------------------------- Яндекс -------------------------------

@router.callback_query(F.data == "cal:connect:yandex")
async def connect_yandex(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ConnectYandex.username)
    await callback.message.answer(
        "🔗 <b>Подключение Яндекс Календаря</b>\n\n"
        "Нужен пароль приложения:\n"
        "1. Открой id.yandex.ru/security/app-passwords\n"
        "2. Нажми «Создать пароль», выбери тип «Календарь».\n"
        "3. Скопируй пароль.\n\n"
        "Пришли свой логин (email на Яндексе):"
    )
    await callback.answer()


@router.message(ConnectYandex.username, F.text)
async def yandex_username(message: Message, state: FSMContext):
    await state.update_data(ydx_username=message.text.strip())
    await state.set_state(ConnectYandex.password)
    await message.answer("Теперь пришли пароль приложения:")


@router.message(ConnectYandex.password, F.text)
async def yandex_password(message: Message, state: FSMContext, db_user: TelegramUser):
    data = await state.get_data()
    username = data.get("ydx_username", "")
    app_password = message.text.strip()
    await state.clear()
    try:
        await _connect_yandex(db_user.pk, username, app_password)
    except Exception as exc:
        logger.warning("Ошибка подключения Яндекс: %s", exc)
        await message.answer("⚠️ Не удалось подключиться. Проверь логин и пароль приложения.")
        return
    await message.answer("✅ Яндекс Календарь подключён!", reply_markup=MAIN_MENU)


@sync_to_async
def _connect_yandex(user_pk, username, app_password):
    user = TelegramUser.objects.get(pk=user_pk)
    conn, _ = CalendarConnection.objects.update_or_create(
        user=user,
        provider="yandex",
        defaults={"credentials": {"username": username, "app_password": app_password}, "is_active": True},
    )
    cal_id = YandexCalendarProvider(conn).validate()
    conn.calendar_id = cal_id
    conn.save(update_fields=["calendar_id"])
    return conn


# ------------------------------ Отключение ------------------------------

@router.callback_query(F.data.startswith("cal:disconnect:"))
async def disconnect(callback: CallbackQuery, db_user: TelegramUser):
    pk = int(callback.data.split(":")[2])
    await sync_to_async(
        lambda: CalendarConnection.objects.filter(pk=pk, user_id=db_user.pk).update(is_active=False)
    )()
    await callback.answer("Отключено")
    connections = await _list_connections(db_user.pk)
    await callback.message.edit_text(
        "📅 <b>Календари</b>\n\nКалендарь отключён.", reply_markup=_calendars_keyboard(connections)
    )


# ------------------------------ Синхронизация ------------------------------

@router.callback_query(F.data == "cal:sync")
async def sync_now(callback: CallbackQuery, db_user: TelegramUser):
    await callback.answer("Синхронизирую…")
    count = await _pull_user(db_user.pk)
    await callback.message.answer(f"✅ Синхронизация завершена. Изменений: {count}.", reply_markup=MAIN_MENU)
