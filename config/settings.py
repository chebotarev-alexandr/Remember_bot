"""Настройки Django-проекта Remember_bot."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Простой загрузчик .env (без внешних зависимостей)
_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _, _value = _line.partition("=")
        os.environ.setdefault(_key.strip(), _value.strip())

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-secret-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "calendar_sync",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DATABASE_PATH", str(BASE_DIR / "db.sqlite3")),
        "OPTIONS": {"timeout": 20},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- Бот ----
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# Лимиты бесплатного тарифа
FREE_REGULAR_LIMIT = int(os.environ.get("FREE_REGULAR_LIMIT", "10"))
FREE_ONCE_LIMIT = int(os.environ.get("FREE_ONCE_LIMIT", "3"))

# ---- Внешний API (e-ink панель и пр.) ----
# Токен для доступа к /api/my-events/ и владелец, чьи события отдаём.
PLANNER_API_TOKEN = os.environ.get("PLANNER_API_TOKEN", "")
PLANNER_OWNER_TELEGRAM_ID = int(os.environ.get("PLANNER_OWNER_TELEGRAM_ID", "401678632"))

# ---- Календари ----
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get(
    "GOOGLE_OAUTH_REDIRECT_URI", "https://bot.code-orbit.ru/callback/google/"
)
YANDEX_OAUTH_CLIENT_ID = os.environ.get("YANDEX_OAUTH_CLIENT_ID", "")
YANDEX_OAUTH_CLIENT_SECRET = os.environ.get("YANDEX_OAUTH_CLIENT_SECRET", "")
YANDEX_OAUTH_REDIRECT_URI = os.environ.get(
    "YANDEX_OAUTH_REDIRECT_URI", "https://bot.code-orbit.ru/callback/yandex/"
)
CALENDAR_EVENT_DURATION_MINUTES = int(os.environ.get("CALENDAR_EVENT_DURATION_MINUTES", "30"))
CALENDAR_SYNC_INTERVAL_SECONDS = int(os.environ.get("CALENDAR_SYNC_INTERVAL_SECONDS", "300"))
