"""Утилиты: часовые пояса и форматирование напоминаний."""

from zoneinfo import ZoneInfo

from core.models import Reminder

WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTH_NAMES = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

# Предустановленные интервалы предупреждения (в минутах)
PRESET_MINUTES = [5, 10, 15, 30, 60, 120, 1440]


def humanize_minutes(n: int | None) -> str:
    """Человекочитаемый интервал: 0 → 'не напоминать', 60 → '1 час', 1440 → '1 день'."""
    if n is None or n <= 0:
        return "не напоминать заранее"
    if n < 60:
        return f"{n} мин"
    hours, minutes = divmod(n, 60)
    if minutes == 0:
        if hours == 1:
            return "1 час"
        if hours == 24:
            return "1 день"
        return f"{hours} ч"
    if hours == 1:
        return f"1 ч {minutes} мин"
    return f"{hours} ч {minutes} мин"

# Курируемый список популярных часовых поясов (IANA name → подпись)
COMMON_TIMEZONES = [
    ("Europe/Moscow", "🇷🇺 Москва (UTC+3)"),
    ("Europe/Kaliningrad", "🇷🇺 Калининград (UTC+2)"),
    ("Europe/Samara", "🇷🇺 Самара (UTC+4)"),
    ("Asia/Yekaterinburg", "🇷🇺 Екатеринбург (UTC+5)"),
    ("Asia/Omsk", "🇷🇺 Омск (UTC+6)"),
    ("Asia/Novosibirsk", "🇷🇺 Новосибирск (UTC+7)"),
    ("Asia/Irkutsk", "🇷🇺 Иркутск (UTC+8)"),
    ("Asia/Yakutsk", "🇷🇺 Якутск (UTC+9)"),
    ("Asia/Vladivostok", "🇷🇺 Владивосток (UTC+10)"),
    ("Asia/Magadan", "🇷🇺 Магадан (UTC+11)"),
    ("Asia/Kamchatka", "🇷🇺 Камчатка (UTC+12)"),
    ("Europe/Minsk", "🇧🇾 Минск (UTC+3)"),
    ("Asia/Almaty", "🇰🇿 Алматы (UTC+5)"),
    ("Asia/Tashkent", "🇺🇿 Ташкент (UTC+5)"),
    ("Asia/Bishkek", "🇰🇬 Бишкек (UTC+6)"),
    ("Asia/Yerevan", "🇦🇲 Ереван (UTC+4)"),
    ("Asia/Tbilisi", "🇬🇪 Тбилиси (UTC+4)"),
    ("Asia/Baku", "🇦🇿 Баку (UTC+4)"),
    ("Europe/London", "🇬🇧 Лондон (UTC+0)"),
    ("Europe/Paris", "🇫🇷 Париж (UTC+1)"),
    ("Europe/Berlin", "🇩🇪 Берлин (UTC+1)"),
    ("Europe/Madrid", "🇪🇸 Мадрид (UTC+1)"),
    ("Europe/Istanbul", "🇹🇷 Стамбул (UTC+3)"),
    ("Asia/Dubai", "🇦🇪 Дубай (UTC+4)"),
    ("Asia/Kolkata", "🇮🇳 Индия (UTC+5:30)"),
    ("Asia/Bangkok", "🇹🇭 Бангкок (UTC+7)"),
    ("Asia/Shanghai", "🇨🇳 Китай (UTC+8)"),
    ("Asia/Tokyo", "🇯🇵 Токио (UTC+9)"),
    ("Asia/Seoul", "🇰🇷 Сеул (UTC+9)"),
    ("Asia/Jerusalem", "🇮🇱 Израиль (UTC+2)"),
    ("America/New_York", "🇺🇸 Нью-Йорк (UTC-5)"),
    ("America/Chicago", "🇺🇸 Чикаго (UTC-6)"),
    ("America/Denver", "🇺🇸 Денвер (UTC-7)"),
    ("America/Los_Angeles", "🇺🇸 Лос-Анджелес (UTC-8)"),
    ("America/Sao_Paulo", "🇧🇷 Сан-Паулу (UTC-3)"),
    ("Australia/Sydney", "🇦🇺 Сидней (UTC+10)"),
    ("Pacific/Auckland", "🇳🇿 Окленд (UTC+12)"),
    ("UTC", "🌐 UTC (UTC+0)"),
]


def tz_label(name: str) -> str:
    for n, label in COMMON_TIMEZONES:
        if n == name:
            return label
    return name


def local_now(timezone_name: str):
    """Локальное 'сейчас' в заданном поясе."""
    from django.utils import timezone

    return timezone.now().astimezone(ZoneInfo(timezone_name or "UTC"))


def occurrence_passed(freq: str, time_val, weekdays, day_of_month, tz_name: str) -> bool:
    """True, если текущее вхождение расписания уже прошло (время наступило)."""
    local = local_now(tz_name)
    if freq == "daily":
        return bool(time_val and local.time() >= time_val)
    if freq == "weekly":
        return bool(time_val and weekdays and local.weekday() in weekdays and local.time() >= time_val)
    if freq == "monthly":
        return bool(time_val and day_of_month and local.day == day_of_month and local.time() >= time_val)
    return False


def format_reminder(r: Reminder, tz_name: str | None = None) -> str:
    """Человекочитаемое описание расписания напоминания."""
    tz_name = tz_name or r.user.timezone or "UTC"
    if r.kind == Reminder.Kind.ONCE and r.remind_at:
        local = r.remind_at.astimezone(ZoneInfo(tz_name))
        return f"⏰ {local:%d.%m.%Y %H:%M}"
    if r.kind == Reminder.Kind.DAILY and r.time:
        return f"🔁 Ежедневно в {r.time:%H:%M}"
    if r.kind == Reminder.Kind.WEEKLY and r.time and r.weekdays:
        days = ", ".join(WEEKDAY_NAMES[d] for d in sorted(r.weekdays))
        return f"🔁 Еженедельно ({days}) в {r.time:%H:%M}"
    if r.kind == Reminder.Kind.MONTHLY and r.time and r.day_of_month:
        return f"🔁 Ежемесячно ({r.day_of_month}-го) в {r.time:%H:%M}"
    return r.get_kind_display()
