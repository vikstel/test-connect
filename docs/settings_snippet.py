"""
Настройки для settings.py — VK ID OAuth 2.1

Скопируйте в ваш settings.py и заполните реальными значениями.
"""

# ─────────────────────────────────────────────
# VK ID OAuth 2.1 (id.vk.com)
# ─────────────────────────────────────────────

# ID приложения из VK ID: id.vk.com/about/business/go → Мои приложения
VK_APP_ID = "your_app_id"

# Защищённый ключ приложения (Client Secret)
VK_APP_SECRET = "your_app_secret"

# Callback URL — должен совпадать с настройками в VK ID
# ВАЖНО: домен должен быть зарегистрирован в VK ID, https обязателен
VK_REDIRECT_URI = "https://yourdomain.com/api/auth/vk/callback/"

# Версия VK API
VK_API_VERSION = "5.199"

# Запрашиваемые права (scope)
# wall     — публикация на стене
# photos   — загрузка фото
# groups   — работа с группами
# offline  — бессрочный токен (VK ID может игнорировать, используйте refresh_token)
VK_OAUTH_SCOPES = "wall,photos,groups,offline"


# ─────────────────────────────────────────────
# Celery Beat: автоматическое обновление токенов
# ─────────────────────────────────────────────
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    # ... ваши существующие задачи ...

    "refresh-vk-tokens": {
        "task": "vk_oauth.tasks.refresh_expiring_vk_tokens",
        "schedule": crontab(minute=0, hour="*/6"),  # каждые 6 часов
    },
}
