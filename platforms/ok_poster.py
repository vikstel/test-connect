import hashlib
import json
import requests
from .base import BasePlatform


class OKPoster(BasePlatform):
    BASE = "https://api.ok.ru/fb.do"

    def __init__(self, access_token: str, group_id: str, application_key: str = None, secret_key: str = None, **kwargs):
        self.access_token = access_token
        self.group_id = group_id
        # application_key и secret_key берутся из env если не переданы
        import os
        self.application_key = application_key or os.getenv("OK_APPLICATION_KEY", "")
        self.secret_key = secret_key or os.getenv("OK_SECRET_KEY", "")
        # session_secret_key вычисляется из access_token + secret_key
        self.session_secret_key = hashlib.md5(
            f"{self.access_token}{self.secret_key}".encode()
        ).hexdigest()

    def _sig(self, params: dict) -> str:
        # sig = MD5(sorted_params_string + session_secret_key)
        sorted_str = "".join(f"{k}={v}" for k, v in sorted(params.items()))
        return hashlib.md5(f"{sorted_str}{self.session_secret_key}".encode()).hexdigest()

    def _call(self, method: str, params: dict) -> dict:
        params.update({
            "application_key": self.application_key,
            "method": method,
            "access_token": self.access_token,
            "format": "json",
        })
        params["sig"] = self._sig({k: v for k, v in params.items() if k != "access_token"})
        r = requests.post(self.BASE, data=params)
        return r.json()

    def test_connection(self) -> dict:
        try:
            result = self._call("users.getCurrentUser", {})
            if "error_code" in result:
                return {"ok": False, "message": result.get("error_msg", "Ошибка")}
            return {"ok": True, "message": f"Подключён как {result.get('name', 'OK User')}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def _upload_photo(self, media_path: str) -> str | None:
        """Загружает фото в группу OK, возвращает photo_id для attachment"""
        # Шаг 1: получить URL для загрузки
        upload_info = self._call("photosV2.getUploadUrl", {
            "gid": self.group_id,
            "count": "1",
        })
        if "error_code" in upload_info:
            raise Exception(f"getUploadUrl error: {upload_info.get('error_msg')}")
        upload_url = upload_info.get("upload_url")
        if not upload_url:
            return None

        # Шаг 2: загрузить файл на upload_url
        with open(media_path, "rb") as f:
            r = requests.post(upload_url, files={"pic1": f})
        upload_result = r.json()

        # Шаг 3: извлечь photo_id и token из ответа загрузки
        # структура: {"photos": {"PHOTO_ID": {"token": "..."}}}
        photos = upload_result.get("photos", {})
        if not photos:
            raise Exception(f"Upload failed: {upload_result}")
        photo_id, photo_data = list(photos.items())[0]
        token = photo_data.get("token")
        if not token:
            return None

        # Шаг 4: commit — передаём photo_id + token
        commit_result = self._call("photosV2.commit", {"photo_id": photo_id, "token": token})
        if "error_code" in commit_result:
            raise Exception(f"photosV2.commit error: {commit_result.get('error_msg')}")

        # Реальный ID фото для attachment
        real_id = commit_result.get("photo_id") or commit_result.get("id")
        if not real_id:
            raise Exception(f"photosV2.commit returned no photo_id: {commit_result}")
        return str(real_id)

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            media_list = []

            # Добавляем фото если есть
            if media_path and media_type == "photo":
                photo_id = self._upload_photo(media_path)
                if photo_id:
                    media_list.append({"type": "photo", "list": [{"id": photo_id}]})

            # Текст всегда добавляем
            media_list.append({"type": "text", "text": text})

            attachment = {"media": media_list}
            result = self._call("mediatopic.post", {
                "gid": self.group_id,
                "type": "GROUP_THEME",
                "attachment": json.dumps(attachment),
            })
            if "error_code" in result:
                return {"ok": False, "message": result.get("error_msg")}
            return {"ok": True, "post_id": str(result)}
        except Exception as e:
            return {"ok": False, "message": str(e)}
