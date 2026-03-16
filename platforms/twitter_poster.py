import requests
from .base import BasePlatform

# OAuth 2.0 user access token используется как Bearer token в заголовке
TWITTER_API = "https://api.twitter.com/2"


class TwitterPoster(BasePlatform):
    def __init__(self, access_token: str, **kwargs):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def test_connection(self) -> dict:
        # GET /users/me недоступен на Free tier (CreditsDepleted)
        # Проверяем только наличие токена — реальный тест произойдёт при публикации
        if self.access_token:
            return {"ok": True, "message": "Twitter токен сохранён (проверка недоступна на Free tier)"}
        return {"ok": False, "message": "Токен отсутствует"}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            # Media upload через v1.1 требует OAuth 1.0a — не поддерживается в OAuth 2.0 flow
            r = requests.post(
                f"{TWITTER_API}/tweets",
                headers=self.headers,
                json={"text": text},
            )
            data = r.json()
            if "errors" in data or "error" in data:
                msg = data.get("errors", [{}])[0].get("message") or data.get("error")
                return {"ok": False, "message": msg}
            if "data" not in data:
                return {"ok": False, "message": f"Unexpected response: {data}"}
            return {"ok": True, "post_id": str(data["data"]["id"])}
        except Exception as e:
            return {"ok": False, "message": str(e)}
