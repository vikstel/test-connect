"""
VKPoster с интеграцией VK ID OAuth 2.1 + PKCE.

Улучшения по сравнению с оригинальной версией:
1. Автоматический refresh токена при ошибке авторизации (коды 5, 1117)
2. Детальное логирование каждого шага загрузки фото
3. Ошибка загрузки фото НЕ проглатывается — пост не публикуется без медиа
4. Поддержка нескольких фото в одном посте через media_paths
5. on_token_refreshed callback для сохранения нового токена в credentials.json
"""

import logging
from typing import Optional

import requests

from .vk_auth_service import refresh_access_token

logger = logging.getLogger(__name__)

VK_API = "https://api.vk.com/method"
VK_V = "5.199"


class VKPoster:
    """
    Клиент для публикации постов в VK через API.

    Args:
        access_token: Токен пользователя (из VK ID OAuth 2.1)
        target_id: ID стены для публикации (отрицательный для группы, например -123456)
        refresh_token: Refresh token для автоматического обновления (опционально)
        on_token_refreshed: Callback для сохранения нового токена в credentials (опционально)
    """

    def __init__(
        self,
        access_token: str,
        target_id: str,
        refresh_token: str = "",
        on_token_refreshed: Optional[callable] = None,
        **kwargs,
    ):
        self.token = access_token
        self.owner_id = int(target_id)
        self.refresh_token = refresh_token
        self.on_token_refreshed = on_token_refreshed

    def _call(self, method: str, **params) -> dict:
        """Вызов VK API метода с автоматическим retry при ошибке авторизации."""
        params.update({"access_token": self.token, "v": VK_V})
        r = requests.post(f"{VK_API}/{method}", data=params)
        data = r.json()

        # Если ошибка авторизации и есть refresh_token — пробуем обновить
        error = data.get("error", {})
        if error.get("error_code") in (5, 1117) and self.refresh_token:
            logger.warning(f"VK API auth error ({error.get('error_code')}), attempting token refresh...")
            refreshed = self._try_refresh_token()
            if refreshed:
                # Повторяем запрос с новым токеном
                params["access_token"] = self.token
                r = requests.post(f"{VK_API}/{method}", data=params)
                data = r.json()

        return data

    def _try_refresh_token(self) -> bool:
        """Попытка обновить токен. Возвращает True если успешно."""
        result = refresh_access_token(self.refresh_token)
        if result["ok"]:
            self.token = result["access_token"]
            self.refresh_token = result["refresh_token"]
            logger.info("VK token refreshed successfully during API call")

            # Уведомляем о новом токене для сохранения в credentials.json
            if self.on_token_refreshed:
                try:
                    self.on_token_refreshed(
                        access_token=self.token,
                        refresh_token=self.refresh_token,
                        expires_in=result.get("expires_in", 0),
                    )
                except Exception as e:
                    logger.error(f"Failed to save refreshed token: {e}")

            return True
        else:
            logger.error(f"VK token refresh failed: {result.get('error')}")
            return False

    def test_connection(self) -> dict:
        """Проверяет подключение: валидность токена и доступность группы."""
        try:
            user_data = self._call("users.get")
            user_ok = "response" in user_data and user_data["response"]

            if self.owner_id < 0:
                group_data = self._call("groups.getById", group_id=abs(self.owner_id))
                if "response" in group_data:
                    resp = group_data["response"]
                    groups = resp.get("groups", resp) if isinstance(resp, dict) else resp
                    if groups:
                        g = groups[0]
                        user_info = ""
                        if user_ok:
                            u = user_data["response"][0]
                            user_info = f" | {u['first_name']} {u['last_name']}"
                        return {"ok": True, "message": f"Группа «{g['name']}»{user_info}"}
                err = group_data.get("error", {}).get("error_msg", "Группа недоступна")
                return {"ok": False, "message": err}

            if user_ok:
                u = user_data["response"][0]
                return {"ok": True, "message": f"Подключён как {u['first_name']} {u['last_name']}"}
            err = user_data.get("error", {}).get("error_msg", "Неизвестная ошибка")
            return {"ok": False, "message": err}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def _upload_photo(self, media_path: str) -> str:
        """
        Загружает фото на стену, возвращает строку attachment.

        Raises:
            Exception: При ошибке на любом шаге (НЕ проглатывается).
        """
        group_id = abs(self.owner_id) if self.owner_id < 0 else 0

        # ── Шаг 1: Получить URL для загрузки ──
        logger.info(f"[VK Upload] Step 1: getWallUploadServer (group_id={group_id})")
        server_resp = self._call("photos.getWallUploadServer", group_id=group_id)

        if "error" in server_resp:
            err = server_resp["error"]
            raise Exception(f"getWallUploadServer [{err.get('error_code')}] {err.get('error_msg')}")

        upload_url = server_resp["response"]["upload_url"]
        logger.info("[VK Upload] Step 1 OK: got upload_url")

        # ── Шаг 2: Загрузить файл на сервер VK ──
        logger.info(f"[VK Upload] Step 2: uploading file {media_path}")
        with open(media_path, "rb") as f:
            upload_resp = requests.post(upload_url, files={"photo": f}, timeout=60)
        uploaded = upload_resp.json()

        # Проверяем что фото реально загрузилось (пустая строка = ошибка)
        if not uploaded.get("photo") or uploaded["photo"] == "[]":
            raise Exception(
                f"Upload failed: VK returned empty photo field. "
                f"Server={uploaded.get('server')}, hash={uploaded.get('hash')}"
            )
        logger.info(f"[VK Upload] Step 2 OK: file uploaded, server={uploaded.get('server')}")

        # ── Шаг 3: Сохранить фото ──
        logger.info("[VK Upload] Step 3: photos.saveWallPhoto")
        save_resp = self._call(
            "photos.saveWallPhoto",
            group_id=group_id,
            photo=uploaded["photo"],
            server=uploaded["server"],
            hash=uploaded["hash"],
        )

        if "error" in save_resp:
            err = save_resp["error"]
            raise Exception(f"saveWallPhoto [{err.get('error_code')}] {err.get('error_msg')}")

        if not save_resp.get("response"):
            raise Exception(f"saveWallPhoto returned empty response: {save_resp}")

        p = save_resp["response"][0]
        attachment = f"photo{p['owner_id']}_{p['id']}"
        logger.info(f"[VK Upload] Step 3 OK: {attachment}")

        return attachment

    def post(
        self,
        text: str,
        media_path: str = None,
        media_paths: list[str] = None,
        media_type: str = None,
        skip_photo_on_error: bool = False,
    ) -> dict:
        """
        Публикация поста на стену.

        Args:
            text: Текст поста
            media_path: Путь к одному файлу фото (обратная совместимость)
            media_paths: Список путей к фото (для нескольких фото)
            media_type: Тип медиа ("photo")
            skip_photo_on_error: True = опубликовать без фото при ошибке загрузки
                                 False (по умолчанию) = вернуть ошибку

        Returns:
            {"ok": True/False, "post_id": "...", "message": "..."}
        """
        try:
            attachments = []
            warnings = []

            # Собираем список файлов для загрузки
            photo_files = []
            if media_paths:
                photo_files = media_paths
            elif media_path and media_type == "photo":
                photo_files = [media_path]

            # Загружаем каждое фото
            for path in photo_files:
                try:
                    attachment = self._upload_photo(path)
                    attachments.append(attachment)
                except Exception as e:
                    error_msg = f"Ошибка загрузки {path}: {e}"
                    logger.error(f"[VK Post] {error_msg}")

                    if skip_photo_on_error:
                        warnings.append(error_msg)
                    else:
                        # НЕ публикуем пост без фото
                        return {"ok": False, "message": error_msg}

            # ── Публикация ──
            params = dict(
                owner_id=self.owner_id,
                message=text,
                attachments=",".join(attachments),
            )

            # from_group=1 — публикуем от имени сообщества
            if self.owner_id < 0:
                params["from_group"] = 1

            result = self._call("wall.post", **params)

            if "error" in result:
                err = result["error"]
                return {"ok": False, "message": f"[{err.get('error_code')}] {err.get('error_msg')}"}

            msg = "Опубликовано"
            if warnings:
                msg += f" (предупреждения: {'; '.join(warnings)})"

            return {
                "ok": True,
                "post_id": str(result["response"]["post_id"]),
                "message": msg,
                "attachments_count": len(attachments),
            }

        except Exception as e:
            logger.exception("[VK Post] Unexpected error")
            return {"ok": False, "message": str(e)}
