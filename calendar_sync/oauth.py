"""Google OAuth 2.0 (Desktop-приложение, loopback + PKCE)."""

import base64
import hashlib
import secrets

import requests
from django.conf import settings

AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def build_auth_url(state: str) -> tuple[str, str]:
    """Возвращает (auth_url, code_verifier)."""
    verifier, challenge = _pkce()
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    qs = "&".join(f"{k}={requests.utils.quote(v)}" for k, v in params.items())
    return f"{AUTH_URI}?{qs}", verifier


def exchange_code(code: str, code_verifier: str) -> dict:
    """Обменивает код авторизации на токены. Возвращает словарь токенов."""
    data = {
        "code": code,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    resp = requests.post(TOKEN_URI, data=data, timeout=30)
    resp.raise_for_status()
    token = resp.json()
    token.setdefault("client_id", settings.GOOGLE_OAUTH_CLIENT_ID)
    token.setdefault("client_secret", settings.GOOGLE_OAUTH_CLIENT_SECRET)
    token.setdefault("token_uri", TOKEN_URI)
    return token
