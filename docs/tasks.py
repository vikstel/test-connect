"""
Celery задача: автоматическое обновление VK токенов.

Токен VK ID живёт ~24 часа (expires_in=86400).
Эта задача обновляет токены заблаговременно, чтобы автопостинг не прерывался.

Добавить в Celery Beat (settings.py):

    CELERY_BEAT_SCHEDULE = {
        "refresh-vk-tokens": {
            "task": "vk_oauth.tasks.refresh_expiring_vk_tokens",
            "schedule": crontab(minute=0, hour="*/6"),  # каждые 6 часов
        },
    }
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .vk_auth_service import refresh_access_token

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def refresh_expiring_vk_tokens(self):
    """
    Находит VK-аккаунты с истекающими токенами и обновляет их.
    Обновляем заранее — за 2 часа до истечения.
    """
    # TODO: Импортировать вашу модель
    # from accounts.models import SocialAccount

    threshold = timezone.now() + timedelta(hours=2)

    # TODO: Раскомментировать когда модель готова
    # expiring_accounts = SocialAccount.objects.filter(
    #     platform="vk",
    #     token_expires_at__lte=threshold,
    #     refresh_token__gt="",  # Есть refresh_token
    # )
    expiring_accounts = []  # заглушка

    refreshed = 0
    failed = 0

    for account in expiring_accounts:
        result = refresh_access_token(account.refresh_token)

        if result["ok"]:
            account.access_token = result["access_token"]
            account.refresh_token = result["refresh_token"]
            account.token_expires_at = timezone.now() + timedelta(seconds=result["expires_in"])
            account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
            refreshed += 1
            logger.info(f"VK token refreshed for account {account.id} (user {account.user_id})")
        else:
            failed += 1
            error = result.get("error", "unknown")
            logger.error(
                f"VK token refresh FAILED for account {account.id}: {error}. "
                f"User {account.user_id} may need to re-authorize."
            )

            # Если refresh_token полностью невалиден — пометить аккаунт
            if error in ("invalid_grant", "invalid_token"):
                account.extra_data["needs_reauth"] = True
                account.save(update_fields=["extra_data", "updated_at"])

    logger.info(f"VK token refresh complete: {refreshed} refreshed, {failed} failed")
    return {"refreshed": refreshed, "failed": failed}


@shared_task
def refresh_single_vk_token(social_account_id: int):
    """
    Обновление токена для одного конкретного аккаунта.
    Вызывается когда API возвращает ошибку авторизации при постинге.
    """
    # TODO: Импортировать вашу модель
    # from accounts.models import SocialAccount

    # account = SocialAccount.objects.get(id=social_account_id, platform="vk")
    # result = refresh_access_token(account.refresh_token)
    #
    # if result["ok"]:
    #     account.access_token = result["access_token"]
    #     account.refresh_token = result["refresh_token"]
    #     account.token_expires_at = timezone.now() + timedelta(seconds=result["expires_in"])
    #     account.save(update_fields=["access_token", "refresh_token", "token_expires_at"])
    #     return {"ok": True}
    # else:
    #     return {"ok": False, "error": result.get("error")}

    logger.info(f"TODO: refresh token for social_account_id={social_account_id}")
    return {"ok": False, "error": "not_implemented"}
