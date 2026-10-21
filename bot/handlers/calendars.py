"""Подключение и синхронизация календарей (Google Calendar, Яндекс Календарь)."""

import logging
import secrets

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from asgiref.sync import sync_to_async
from django.conf import settings

from bot.keyboards.main import MAIN_MENU
from calendar_sync import oauth
from calendar_sync.models import CalendarConnection, PendingOAuth
from calendar_sync.sync import pull_connection
from core.models import TelegramUser

logger = logging.getLogger(__name__)

router = Router()


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
def _save_pending(user_pk, state, provider, verifier):
    PendingOAuth.objects.create(user_id=user_pk, state=state, provider=provider, code_verifier=verifier)


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
        text += "\nСобытия синхронизируются в обе стороны. Нажми на подключение, чтобы отключить."
    else:
        text = "📅 <b>Календари</b>\n\nПодключи календарь — события будут синхронизироваться в обе стороны."
    await message.answer(text, reply_markup=_calendars_keyboard(connections))


# ------------------------------- Google -------------------------------

@router.callback_query(F.data == "cal:connect:google")
async def connect_google(callback: CallbackQuery, db_user: TelegramUser):
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        await callback.message.answer("⚠️ Google OAuth не настроен на сервере (GOOGLE_OAUTH_CLIENT_ID).")
        await callback.answer()
        return
    state = secrets.token_urlsafe(16)
    auth_url, verifier = oauth.build_google_auth_url(state)
    await _save_pending(db_user.pk, state, "google", verifier)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔗 Авторизоваться в Google", url=auth_url)]]
    )
    await callback.message.answer(
        "Нажми кнопку и разреши доступ к календарю. После авторизации откроется страница «Подключено» — и всё готово.",
        reply_markup=kb,
    )
    await callback.answer()


# ------------------------------- Яндекс -------------------------------

@router.callback_query(F.data == "cal:connect:yandex")
async def connect_yandex(callback: CallbackQuery, db_user: TelegramUser):
    if not settings.YANDEX_OAUTH_CLIENT_ID:
        await callback.message.answer("⚠️ Яндекс OAuth не настроен на сервере (YANDEX_OAUTH_CLIENT_ID).")
        await callback.answer()
        return
    state = secrets.token_urlsafe(16)
    auth_url = oauth.build_yandex_auth_url(state)
    await _save_pending(db_user.pk, state, "yandex", "")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔗 Авторизоваться в Яндексе", url=auth_url)]]
    )
    await callback.message.answer(
        "Нажми кнопку и разреши доступ к календарю. После авторизации откроется страница «Подключено» — и всё готово.",
        reply_markup=kb,
    )
    await callback.answer()


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
