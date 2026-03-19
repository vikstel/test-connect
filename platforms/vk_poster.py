import requests
from .base import BasePlatform

VK_API = "https://api.vk.com/method"
VK_V = "5.199"


class VKPoster(BasePlatform):
    def __init__(self, access_token: str, target_id: str, **kwargs):
        self.token = access_token
        self.owner_id = int(target_id)

    def _call(self, method: str, **params) -> dict:
        params.update({"access_token": self.token, "v": VK_V})
        r = requests.post(f"{VK_API}/{method}", data=params)
        return r.json()

    def test_connection(self) -> dict:
        try:
            # Проверяем пользователя (user token via OAuth)
            user_data = self._call("users.get")
            user_ok = "response" in user_data and user_data["response"]

            # Проверяем доступность группы
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

    def _upload_photo(self, media_path: str) -> str | None:
        """Загружает фото на стену группы, возвращает строку attachment типа photo-ID_ID"""
        # Шаг 1: получить URL для загрузки
        server_resp = self._call("photos.getWallUploadServer", group_id=abs(self.owner_id))
        if "error" in server_resp:
            err = server_resp["error"]
            raise Exception(f"getWallUploadServer [{err.get('error_code')}] {err.get('error_msg')}")

        upload_url = server_resp["response"]["upload_url"]

        # Шаг 2: загрузить файл
        with open(media_path, "rb") as f:
            uploaded = requests.post(upload_url, files={"photo": f}).json()

        # Шаг 3: сохранить фото
        save_resp = self._call(
            "photos.saveWallPhoto",
            group_id=abs(self.owner_id),
            photo=uploaded["photo"],
            server=uploaded["server"],
            hash=uploaded["hash"],
        )
        if "error" in save_resp:
            err = save_resp["error"]
            raise Exception(f"saveWallPhoto [{err.get('error_code')}] {err.get('error_msg')}")

        p = save_resp["response"][0]
        # owner_id уже отрицательный для групп (например -123456)
        return f"photo{p['owner_id']}_{p['id']}"

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            attachments = []
            photo_skipped = None

            if media_path and media_type == "photo":
                try:
                    attachment = self._upload_photo(media_path)
                    attachments.append(attachment)
                except Exception as e:
                    photo_skipped = str(e)

            params = dict(
                owner_id=self.owner_id,
                message=text,  # текст + эмодзи — Unicode, VK принимает нативно
                attachments=",".join(attachments),
            )
            # from_group=1 — публикуем от имени сообщества (community token)
            if self.owner_id < 0:
                params["from_group"] = 1

            result = self._call("wall.post", **params)
            if "error" in result:
                err = result["error"]
                return {"ok": False, "message": f"[{err.get('error_code')}] {err.get('error_msg')}"}

            msg = "Опубликовано" + (f" (фото пропущено: {photo_skipped})" if photo_skipped else "")
            return {"ok": True, "post_id": str(result["response"]["post_id"]), "message": msg}
        except Exception as e:
            return {"ok": False, "message": str(e)}
