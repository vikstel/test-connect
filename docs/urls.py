"""
URL конфигурация для VK ID OAuth 2.1

Подключение в основном urls.py проекта:
    path("", include("vk_oauth.urls")),
"""

from django.urls import path
from . import views

app_name = "vk_oauth"

urlpatterns = [
    # Начало авторизации: редирект на VK ID
    path("api/auth/vk/", views.vk_auth_start, name="start"),

    # Callback: VK ID возвращает сюда с code
    path("api/auth/vk/callback/", views.vk_auth_callback, name="callback"),

    # Обновление токена (ручной вызов / API)
    path("api/auth/vk/refresh/", views.vk_refresh_token, name="refresh"),
]
