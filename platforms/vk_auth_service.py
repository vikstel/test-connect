"""
VK ID OAuth 2.1 + PKCE — Сервис авторизации (адаптирован под FastAPI / os.getenv)

Полный flow:
1. Генерация PKCE (code_verifier + code_challenge)
2. Редирект пользователя на VK ID для авторизации
3. Обмен authorization code на access_token + refresh_token
4. Обновление токена через refresh_token
5. Хелпер для получения информации о пользователе

Переменные окружения (.env):
  VK_APP_ID     — ID приложения из id.vk.com
  VK_APP_SECRET — Защищённый ключ приложения
  VK_REDIRECT_URI — https://yourdomain.com/oauth/vk/callback
  VK_API_VERSION  — версия VK API (по умолчанию 5.199)
  VK_OAUTH_SCOPES — права (по умолчанию wall,photos,groups,offline)
"""

import base64
import hashlib
import os
import secrets
import logging
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Эндпоинты VK ID (OAuth 2.1)
# ─────────────────────────────────────────────
VK_ID_AUTHORIZE_URL = "https://id.vk.com/authorize"
VK_ID_TOKEN_URL = "https://id.vk.com/oauth2/auth"
VK_ID_USER_INFO_URL = "https://id.vk.com/oauth2/user_info"
VK_API_BASE = "https://api.vk.com/method"


def _setting(key: str, default: str = "") -> str:
    """Получить значение из env-переменной."""
    return os.getenv(key, default)


# ─────────────────────────────────────────────
# 1. PKCE: генерация code_verifier и code_challenge
# ─────────────────────────────────────────────
def generate_pkce_pair() -> tuple[str, str]:
    """
    Генерирует пару (code_verifier, code_challenge) для PKCE S256.

    code_verifier — случайная строка 43-128 символов (URL-safe).
    code_challenge — SHA256 хэш от code_verifier в Base64 URL encoding.

    Returns:
        (code_verifier, code_challenge)
    """
    # 32 байта → 43 символа в base64url (без padding)
    code_verifier = secrets.token_urlsafe(32)

    # S256: code_challenge = BASE64URL(SHA256(code_verifier))
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    return code_verifier, code_challenge


# ─────────────────────────────────────────────
# 2. Формирование URL авторизации
# ─────────────────────────────────────────────
def get_authorization_url(state: str | None = None) -> dict:
    """
    Формирует URL для редиректа пользователя на страницу авторизации VK ID.

    Returns:
        {
            "url": "https://id.vk.com/authorize?...",
            "state": "...",
            "code_verifier": "..."  # СОХРАНИТЬ В СЕССИЮ/ФАЙЛ!
        }
    """
    if state is None:
        state = secrets.token_urlsafe(16)

    code_verifier, code_challenge = generate_pkce_pair()

    params = {
        "response_type": "code",
        "client_id": _setting("VK_APP_ID"),
        "redirect_uri": _setting("VK_REDIRECT_URI"),
        "scope": _setting("VK_OAUTH_SCOPES", "wall,photos,groups,offline"),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    url = f"{VK_ID_AUTHORIZE_URL}?{urlencode(params)}"

    return {
        "url": url,
        "state": state,
        "code_verifier": code_verifier,
    }


# ─────────────────────────────────────────────
# 3. Обмен authorization code → access_token
# ─────────────────────────────────────────────
def exchange_code_for_token(code: str, code_verifier: str, device_id: str = "") -> dict:
    """
    Обменивает authorization code на access_token и refresh_token.

    Returns:
        {
            "ok": True/False,
            "access_token": "...",
            "refresh_token": "...",
            "expires_in": 86400,
            "user_id": 123456,
            "error": "..." (если ok=False)
        }
    """
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "client_id": _setting("VK_APP_ID"),
        "client_secret": _setting("VK_APP_SECRET"),
        "redirect_uri": _setting("VK_REDIRECT_URI"),
    }

    if device_id:
        payload["device_id"] = device_id

    try:
        resp = requests.post(VK_ID_TOKEN_URL, data=payload, timeout=15)
        data = resp.json()

        if "access_token" in data:
            logger.info(f"VK OAuth: token obtained, user_id={data.get('user_id')}")
            return {
                "ok": True,
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 0),
                "user_id": data.get("user_id"),
            }
        else:
            error = data.get("error", "unknown_error")
            error_desc = data.get("error_description", "")
            logger.error(f"VK OAuth token error: {error} — {error_desc}")
            return {
                "ok": False,
                "error": error,
                "error_description": error_desc,
            }

    except requests.RequestException as e:
        logger.exception("VK OAuth: network error during token exchange")
        return {"ok": False, "error": "network_error", "error_description": str(e)}


# ─────────────────────────────────────────────
# 4. Обновление токена через refresh_token
# ─────────────────────────────────────────────
def refresh_access_token(refresh_token: str) -> dict:
    """
    Обновляет access_token по refresh_token.

    VK ID выдаёт новый access_token + новый refresh_token.
    Старый refresh_token после использования становится невалидным.

    Returns:
        {
            "ok": True/False,
            "access_token": "...",
            "refresh_token": "...",  # НОВЫЙ! Сохранить вместо старого.
            "expires_in": 86400,
        }
    """
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": _setting("VK_APP_ID"),
        "client_secret": _setting("VK_APP_SECRET"),
    }

    try:
        resp = requests.post(VK_ID_TOKEN_URL, data=payload, timeout=15)
        data = resp.json()

        if "access_token" in data:
            logger.info("VK OAuth: token refreshed successfully")
            return {
                "ok": True,
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 0),
            }
        else:
            error = data.get("error", "unknown_error")
            error_desc = data.get("error_description", "")
            logger.warning(f"VK OAuth refresh error: {error} — {error_desc}")
            return {
                "ok": False,
                "error": error,
                "error_description": error_desc,
            }

    except requests.RequestException as e:
        logger.exception("VK OAuth: network error during token refresh")
        return {"ok": False, "error": "network_error", "error_description": str(e)}


# ─────────────────────────────────────────────
# 5. Получение информации о пользователе
# ─────────────────────────────────────────────
def get_user_info(access_token: str) -> dict:
    """
    Получает информацию о пользователе через VK ID.

    Returns:
        {"ok": True, "user": {"user_id": ..., "first_name": ..., ...}}
    """
    payload = {
        "access_token": access_token,
        "client_id": _setting("VK_APP_ID"),
    }

    try:
        resp = requests.post(VK_ID_USER_INFO_URL, data=payload, timeout=10)
        data = resp.json()

        if "user" in data:
            return {"ok": True, "user": data["user"]}
        else:
            return {"ok": False, "error": data.get("error", "unknown")}

    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────
# 6. Хелпер: вызов VK API метода с токеном
# ─────────────────────────────────────────────
def call_vk_api(method: str, access_token: str, **params) -> dict:
    """
    Универсальный вызов VK API метода.

    Args:
        method: Название метода, например "wall.post" или "photos.getWallUploadServer"
        access_token: Токен пользователя
        **params: Параметры метода

    Returns:
        Сырой ответ VK API (dict)
    """
    params["access_token"] = access_token
    params["v"] = _setting("VK_API_VERSION", "5.199")

    try:
        resp = requests.post(f"{VK_API_BASE}/{method}", data=params, timeout=30)
        return resp.json()
    except requests.RequestException as e:
        logger.exception(f"VK API call error: {method}")
        return {"error": {"error_code": -1, "error_msg": str(e)}}
