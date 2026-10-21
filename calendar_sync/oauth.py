"""OAuth 2.0 для Google Calendar и Яндекс Календаря (web-флоу с редиректом)."""

import base64
import hashlib
import secrets

import requests
from django.conf import settings

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar"]

YANDEX_AUTH_URI = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URI = "https://oauth.yandex.ru/token"
YANDEX_SCOPES = "calendar:all"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


# ------------------------------- Google -------------------------------

def build_google_auth_url(state: str) -> tuple[str, str]:
    """Возвращает (auth_url, code_verifier)."""
    verifier, challenge = _pkce()
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    qs = "&".join(f"{k}={requests.utils.quote(v)}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URI}?{qs}", verifier


def exchange_google_code(code: str, code_verifier: str) -> dict:
    data = {
        "code": code,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    resp = requests.post(GOOGLE_TOKEN_URI, data=data, timeout=30)
    resp.raise_for_status()
    token = resp.json()
    token.setdefault("client_id", settings.GOOGLE_OAUTH_CLIENT_ID)
    token.setdefault("client_secret", settings.GOOGLE_OAUTH_CLIENT_SECRET)
    token.setdefault("token_uri", GOOGLE_TOKEN_URI)
    return token


# ------------------------------- Яндекс -------------------------------

def build_yandex_auth_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.YANDEX_OAUTH_CLIENT_ID,
        "redirect_uri": settings.YANDEX_OAUTH_REDIRECT_URI,
        "scope": YANDEX_SCOPES,
        "state": state,
    }
    qs = "&".join(f"{k}={requests.utils.quote(v)}" for k, v in params.items())
    return f"{YANDEX_AUTH_URI}?{qs}"


def exchange_yandex_code(code: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.YANDEX_OAUTH_CLIENT_ID,
        "client_secret": settings.YANDEX_OAUTH_CLIENT_SECRET,
    }
    resp = requests.post(YANDEX_TOKEN_URI, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()  # {access_token, refresh_token, expires_in, token_type}
