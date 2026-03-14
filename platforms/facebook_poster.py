import requests
from .base import BasePlatform


class FacebookPoster(BasePlatform):
    BASE = "https://graph.facebook.com/v25.0"

    def __init__(self, page_access_token: str, page_id: str):
        self.token = page_access_token
        self.page_id = page_id

    def test_connection(self) -> dict:
        try:
            r = requests.get(f"{self.BASE}/{self.page_id}", params={
                "fields": "name,id",
                "access_token": self.token
            })
            data = r.json()
            if "error" in data:
                return {"ok": False, "message": data["error"]["message"]}
            return {"ok": True, "message": f"Страница: {data['name']}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            if media_path and media_type == "photo":
                with open(media_path, "rb") as f:
                    r = requests.post(f"{self.BASE}/{self.page_id}/photos", data={
                        "caption": text,
                        "access_token": self.token
                    }, files={"source": f})
            else:
                r = requests.post(f"{self.BASE}/{self.page_id}/feed", data={
                    "message": text,
                    "access_token": self.token
                })
            data = r.json()
            if "error" in data:
                return {"ok": False, "message": data["error"]["message"]}
            return {"ok": True, "post_id": data.get("id", data.get("post_id"))}
        except Exception as e:
            return {"ok": False, "message": str(e)}
