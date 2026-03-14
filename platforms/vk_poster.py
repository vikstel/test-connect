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
            data = self._call("users.get")
            if "response" in data and data["response"]:
                u = data["response"][0]
                return {"ok": True, "message": f"Подключён как {u['first_name']} {u['last_name']}"}
            # Group token — check group info
            data = self._call("groups.getById", group_id=abs(self.owner_id))
            if "response" in data:
                resp = data["response"]
                # API 5.199 returns {"groups": [...]} , older returns [...]
                groups = resp.get("groups", resp) if isinstance(resp, dict) else resp
                if groups:
                    g = groups[0]
                    return {"ok": True, "message": f"Группа «{g['name']}»"}
            err = data.get("error", {}).get("error_msg", "Неизвестная ошибка")
            return {"ok": False, "message": err}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            attachments = []
            photo_skipped = False
            if media_path and media_type == "photo":
                server_resp = self._call("photos.getWallUploadServer", group_id=abs(self.owner_id))
                if "error" in server_resp:
                    # Community tokens can't upload photos — post text only
                    photo_skipped = True
                else:
                    upload_url = server_resp["response"]["upload_url"]
                    with open(media_path, "rb") as f:
                        uploaded = requests.post(upload_url, files={"photo": f}).json()
                    save_resp = self._call("photos.saveWallPhoto",
                        group_id=abs(self.owner_id),
                        photo=uploaded["photo"],
                        server=uploaded["server"],
                        hash=uploaded["hash"],
                    )
                    if "error" in save_resp:
                        photo_skipped = True
                    else:
                        p = save_resp["response"][0]
                        attachments.append(f"photo{p['owner_id']}_{p['id']}")

            params = dict(owner_id=self.owner_id, message=text, attachments=",".join(attachments))
            if self.owner_id < 0:
                params["from_group"] = 1

            result = self._call("wall.post", **params)
            if "error" in result:
                return {"ok": False, "message": result["error"]["error_msg"]}
            msg = "Опубликовано" + (" (без фото — community токен не поддерживает загрузку фото)" if photo_skipped else "")
            return {"ok": True, "post_id": str(result["response"]["post_id"]), "message": msg}
        except Exception as e:
            return {"ok": False, "message": str(e)}
