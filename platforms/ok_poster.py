import hashlib
import json
import requests
from .base import BasePlatform


class OKPoster(BasePlatform):
    BASE = "https://api.ok.ru/fb.do"

    def __init__(self, access_token: str, session_secret_key: str, application_key: str, secret_key: str, group_id: str):
        self.access_token = access_token
        self.session_secret_key = session_secret_key
        self.application_key = application_key
        self.secret_key = secret_key
        self.group_id = group_id

    def _sig(self, params: dict) -> str:
        secret_md5 = hashlib.md5(f"{self.access_token}{self.secret_key}".encode()).hexdigest()
        sorted_str = "".join(f"{k}={v}" for k, v in sorted(params.items()))
        return hashlib.md5(f"{sorted_str}{secret_md5}".encode()).hexdigest()

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

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            attachment = {"media": [{"type": "text", "text": text}]}
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
