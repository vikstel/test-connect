import requests
from .base import BasePlatform


class InstagramPoster(BasePlatform):
    BASE = "https://graph.facebook.com/v25.0"

    def __init__(self, access_token: str, user_id: str):
        self.token = access_token
        self.user_id = user_id

    def test_connection(self) -> dict:
        try:
            r = requests.get(f"{self.BASE}/{self.user_id}", params={
                "fields": "id,username",
                "access_token": self.token
            })
            data = r.json()
            if "error" in data:
                return {"ok": False, "message": data["error"]["message"]}
            return {"ok": True, "message": f"Instagram: @{data.get('username', data['id'])}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            if not media_path:
                return {"ok": False, "message": "Instagram требует медиафайл (публичный HTTPS URL)"}
            # media_path должен быть публичным URL
            r = requests.post(f"{self.BASE}/{self.user_id}/media", data={
                "image_url": media_path,
                "caption": text,
                "access_token": self.token
            })
            data = r.json()
            if "error" in data:
                return {"ok": False, "message": data["error"]["message"]}
            creation_id = data["id"]
            r2 = requests.post(f"{self.BASE}/{self.user_id}/media_publish", data={
                "creation_id": creation_id,
                "access_token": self.token
            })
            data2 = r2.json()
            if "error" in data2:
                return {"ok": False, "message": data2["error"]["message"]}
            return {"ok": True, "post_id": data2.get("id")}
        except Exception as e:
            return {"ok": False, "message": str(e)}
