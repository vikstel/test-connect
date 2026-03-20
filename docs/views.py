"""
Django Views для VK ID OAuth 2.1 — BlogToSocial

URL-конфигурация (urls.py):
    path("api/auth/vk/", views.vk_auth_start, name="vk_auth_start"),
    path("api/auth/vk/callback/", views.vk_auth_callback, name="vk_auth_callback"),
    path("api/auth/vk/refresh/", views.vk_refresh_token, name="vk_refresh_token"),
"""

import logging

from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required

from .vk_auth_service import (
    get_authorization_url,
    exchange_code_for_token,
    refresh_access_token,
    get_user_info,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Шаг 1: Начало авторизации — редирект на VK ID
# ─────────────────────────────────────────────
@login_required
@require_GET
def vk_auth_start(request):
    """
    Пользователь нажимает «Подключить VK» в интерфейсе BlogToSocial.
    Генерируем PKCE, сохраняем в сессию, редиректим на VK ID.
    """
    auth_data = get_authorization_url()

    # Сохраняем в сессию для проверки при callback
    request.session["vk_oauth_state"] = auth_data["state"]
    request.session["vk_oauth_code_verifier"] = auth_data["code_verifier"]

    logger.info(f"VK OAuth: redirecting user {request.user.id} to VK ID")
    return redirect(auth_data["url"])


# ─────────────────────────────────────────────
# Шаг 2: Callback — VK ID вернул code
# ─────────────────────────────────────────────
@login_required
@require_GET
def vk_auth_callback(request):
    """
    VK ID редиректит сюда после авторизации пользователя.
    URL содержит: ?code=...&state=...&device_id=...

    Проверяем state, обмениваем code на token, сохраняем.
    """
    code = request.GET.get("code")
    state = request.GET.get("state")
    device_id = request.GET.get("device_id", "")
    error = request.GET.get("error")

    # ── Обработка ошибки от VK ──
    if error:
        error_desc = request.GET.get("error_description", "")
        logger.warning(f"VK OAuth error from VK ID: {error} — {error_desc}")
        return JsonResponse(
            {"ok": False, "error": error, "message": error_desc},
            status=400,
        )

    # ── Проверка наличия code ──
    if not code:
        return JsonResponse(
            {"ok": False, "error": "missing_code", "message": "Код авторизации не получен"},
            status=400,
        )

    # ── Проверка CSRF (state) ──
    saved_state = request.session.pop("vk_oauth_state", None)
    if state != saved_state:
        logger.warning(f"VK OAuth: state mismatch. Expected={saved_state}, got={state}")
        return JsonResponse(
            {"ok": False, "error": "invalid_state", "message": "Ошибка безопасности (state mismatch)"},
            status=403,
        )

    # ── Извлекаем code_verifier из сессии ──
    code_verifier = request.session.pop("vk_oauth_code_verifier", None)
    if not code_verifier:
        return JsonResponse(
            {"ok": False, "error": "missing_verifier", "message": "Сессия истекла, попробуйте ещё раз"},
            status=400,
        )

    # ── Обмен code → token ──
    result = exchange_code_for_token(code, code_verifier, device_id)

    if not result["ok"]:
        return JsonResponse(result, status=400)

    # ── Получаем информацию о пользователе VK ──
    user_info = get_user_info(result["access_token"])

    # ── Сохраняем токены в БД ──
    # TODO: Заменить на вашу модель SocialAccount / VKConnection
    _save_vk_tokens(
        user=request.user,
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
        vk_user_id=result.get("user_id"),
        vk_user_info=user_info.get("user", {}),
    )

    logger.info(f"VK OAuth: user {request.user.id} connected VK account {result.get('user_id')}")

    # Редирект обратно в интерфейс BlogToSocial
    # TODO: Заменить на ваш фронтенд URL
    return redirect("/dashboard/accounts/?connected=vk")


# ─────────────────────────────────────────────
# Шаг 3: Обновление токена (вызывается из Celery / бэкенда)
# ─────────────────────────────────────────────
@login_required
@require_POST
def vk_refresh_token(request):
    """
    Обновляет VK access_token по refresh_token.
    Вызывается когда токен истёк (expires_in обычно 86400 сек = 24 часа).
    """
    # TODO: Достать refresh_token из вашей модели
    refresh_token = request.POST.get("refresh_token", "")

    if not refresh_token:
        return JsonResponse(
            {"ok": False, "error": "missing_refresh_token"},
            status=400,
        )

    result = refresh_access_token(refresh_token)

    if result["ok"]:
        # TODO: Обновить токены в БД
        # ВАЖНО: refresh_token тоже обновляется! Старый становится невалидным.
        _save_vk_tokens(
            user=request.user,
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=result["expires_in"],
        )

    return JsonResponse(result)


# ─────────────────────────────────────────────
# Заглушка: сохранение токенов в БД
# ─────────────────────────────────────────────
def _save_vk_tokens(
    user,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    vk_user_id: int | None = None,
    vk_user_info: dict | None = None,
):
    """
    TODO: Реализовать сохранение токенов в вашу модель.

    Примерная модель:

        class SocialAccount(models.Model):
            user = models.ForeignKey(User, on_delete=models.CASCADE)
            platform = models.CharField(max_length=20)  # "vk"
            platform_user_id = models.CharField(max_length=50)
            access_token = models.TextField()
            refresh_token = models.TextField(blank=True)
            token_expires_at = models.DateTimeField()
            extra_data = models.JSONField(default=dict)
            created_at = models.DateTimeField(auto_now_add=True)
            updated_at = models.DateTimeField(auto_now=True)

    Важно:
    - Шифруйте access_token и refresh_token в БД (django-fernet-fields / django-encrypted-fields)
    - Обновляйте token_expires_at при каждом refresh
    - refresh_token одноразовый: после использования VK выдаёт новый
    """
    logger.info(
        f"TODO: save VK tokens for user={user.id}, "
        f"vk_user_id={vk_user_id}, expires_in={expires_in}"
    )
