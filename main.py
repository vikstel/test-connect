import json
import os
import uuid
import shutil
import secrets
import hashlib
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import requests as http_requests

from config import load_credentials, save_platform, clear_platform, get_platform_config

load_dotenv(override=True)

app = FastAPI()

Path("uploads").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

PLATFORM_MAP = {
    "telegram": ("platforms.telegram_poster", "TelegramPoster"),
    "vk": ("platforms.vk_poster", "VKPoster"),
    "ok": ("platforms.ok_poster", "OKPoster"),
    "facebook": ("platforms.facebook_poster", "FacebookPoster"),
    "instagram": ("platforms.instagram_poster", "InstagramPoster"),
    "twitter": ("platforms.twitter_poster", "TwitterPoster"),
    "zen": ("platforms.zen_poster", "ZenPoster"),
}

VK_REDIRECT_URI = os.getenv("VK_REDIRECT_URI", "https://test-connect-production-2101.up.railway.app/oauth/vk/callback")
OK_REDIRECT_URI = "https://test-connect-production-2101.up.railway.app/oauth/ok/callback"
TWITTER_REDIRECT_URI = "https://test-connect-production-2101.up.railway.app/oauth/twitter/callback"
FACEBOOK_REDIRECT_URI = "https://test-connect-production-2101.up.railway.app/oauth/facebook/callback"


def get_poster(platform: str):
    cfg = get_platform_config(platform)
    if not cfg or platform not in PLATFORM_MAP:
        return None
    module_path, class_name = PLATFORM_MAP[platform]
    import importlib
    module = importlib.import_module(module_path)

    # Для VK добавляем callback для автосохранения обновлённого токена
    if platform == "vk":
        def on_vk_token_refreshed(access_token: str, refresh_token: str, expires_in: int):
            """Сохраняет новый токен после автоматического refresh."""
            updated_cfg = get_platform_config("vk")
            updated_cfg["access_token"] = access_token
            updated_cfg["refresh_token"] = refresh_token
            save_platform("vk", updated_cfg)

        cfg = {**cfg, "on_token_refreshed": on_vk_token_refreshed}

    return getattr(module, class_name)(**cfg)


def execute_post(platforms: list, text: str, media_path: str = None, media_type: str = None):
    results = {}
    for p in platforms:
        poster = get_poster(p)
        results[p] = poster.post(text, media_path, media_type) if poster else {"ok": False, "message": "Не настроено"}
    return results


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/zen_{token}.html")
def zen_verification(token: str):
    """Верификационный файл для Яндекс Дзен"""
    path = Path(f"static/zen_{token}.html")
    if path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "not found"}, status_code=404)


@app.get("/api/status")
def status():
    creds = load_credentials()
    return {p: ("configured" if creds.get(p) else "not_configured") for p in PLATFORM_MAP}


@app.post("/api/connect/{platform}")
async def connect(platform: str, request: Request):
    data = await request.json()
    save_platform(platform, data)
    return {"ok": True}


@app.delete("/api/connect/{platform}")
def disconnect(platform: str):
    clear_platform(platform)
    return {"ok": True}


@app.post("/api/test/{platform}")
def test_platform(platform: str):
    poster = get_poster(platform)
    if not poster:
        return {"ok": False, "message": "Платформа не настроена"}
    return poster.test_connection()


@app.post("/api/post")
async def post_now(
    text: str = Form(...),
    platforms: List[str] = Form(...),
    file: Optional[UploadFile] = File(None),
):
    media_path = None
    media_type = None
    if file and file.filename:
        media_path = f"uploads/{uuid.uuid4()}_{file.filename}"
        with open(media_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        ext = file.filename.rsplit(".", 1)[-1].lower()
        media_type = "video" if ext in ("mp4", "mov", "avi", "mkv") else "photo"
    return execute_post(platforms, text, media_path, media_type)


@app.post("/api/schedule")
async def schedule(
    text: str = Form(...),
    platforms: List[str] = Form(...),
    run_at: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    from scheduler import schedule_post
    media_path = None
    if file and file.filename:
        media_path = f"uploads/{uuid.uuid4()}_{file.filename}"
        with open(media_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    job_id = str(uuid.uuid4())
    schedule_post(job_id, datetime.fromisoformat(run_at), platforms, text, media_path)
    return {"ok": True, "job_id": job_id}


@app.get("/api/jobs")
def get_jobs():
    from scheduler import list_jobs
    return list_jobs()


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    from scheduler import cancel_job
    return {"ok": cancel_job(job_id)}


# ─── VK OAuth 2.1 + PKCE (id.vk.com) ────────────────────────────
# Используем VK ID OAuth 2.1 с PKCE — даёт access_token + refresh_token.
# state/code_verifier сохраняем в файл (как ok_state.json), сессий нет.

_VK_PKCE_FILE = Path("vk_pkce.json")


def _vk_pkce_save(state: str, code_verifier: str, target_id: str = ""):
    """Сохраняем PKCE-данные и target_id по ключу state."""
    data = {}
    if _VK_PKCE_FILE.exists():
        data = json.loads(_VK_PKCE_FILE.read_text())
    data[state] = {"code_verifier": code_verifier, "target_id": target_id}
    _VK_PKCE_FILE.write_text(json.dumps(data))


def _vk_pkce_pop(state: str) -> dict:
    """Извлекаем и удаляем PKCE-данные по state."""
    if not _VK_PKCE_FILE.exists():
        return {}
    data = json.loads(_VK_PKCE_FILE.read_text())
    entry = data.pop(state, {})
    _VK_PKCE_FILE.write_text(json.dumps(data))
    return entry


@app.get("/oauth/vk")
def vk_oauth_start(target_id: str = ""):
    """Редирект на VK ID OAuth 2.1 с PKCE. target_id сохраняется вместе с code_verifier."""
    from platforms.vk_auth_service import get_authorization_url
    app_id = os.getenv("VK_APP_ID")
    if not app_id:
        return JSONResponse({"error": "VK_APP_ID не найден в .env"}, status_code=400)

    auth_data = get_authorization_url()
    # Сохраняем code_verifier и target_id для проверки в callback
    _vk_pkce_save(auth_data["state"], auth_data["code_verifier"], target_id)

    return RedirectResponse(auth_data["url"])


@app.get("/oauth/vk/callback")
def vk_oauth_callback(code: str = None, state: str = None, device_id: str = "", error: str = None):
    """
    Callback от VK ID OAuth 2.1.
    VK передаёт ?code=...&state=...&device_id=... (Authorization Code Flow).
    """
    from platforms.vk_auth_service import exchange_code_for_token, get_user_info

    # Обработка ошибки от VK
    if error:
        return RedirectResponse(f"/?vk_error={error}")

    if not code:
        return RedirectResponse("/?vk_error=no_code")

    # Извлекаем сохранённые данные PKCE
    pkce_data = _vk_pkce_pop(state) if state else {}
    if not pkce_data:
        return RedirectResponse("/?vk_error=invalid_state")

    code_verifier = pkce_data.get("code_verifier", "")
    target_id = pkce_data.get("target_id", "")

    # Обмениваем code на токен
    result = exchange_code_for_token(code, code_verifier, device_id)

    if not result["ok"]:
        err = result.get("error", "token_error")
        return RedirectResponse(f"/?vk_error={err}")

    # Сохраняем токены в credentials.json
    vk_cfg = {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
    }
    if target_id:
        vk_cfg["target_id"] = target_id

    save_platform("vk", vk_cfg)
    return RedirectResponse("/?vk_connected=1")


# ─── OK OAuth ────────────────────────────────────────────────────
_OK_STATE_FILE = Path("ok_state.json")


def _ok_state_save(state: str, group_id: str):
    data = {}
    if _OK_STATE_FILE.exists():
        data = json.loads(_OK_STATE_FILE.read_text())
    data[state] = group_id
    _OK_STATE_FILE.write_text(json.dumps(data))


def _ok_state_pop(state: str):
    if not _OK_STATE_FILE.exists():
        return None
    data = json.loads(_OK_STATE_FILE.read_text())
    group_id = data.pop(state, None)
    _OK_STATE_FILE.write_text(json.dumps(data))
    return group_id


@app.get("/oauth/ok")
def ok_oauth_start(group_id: str = None):
    app_id = os.getenv("OK_APP_ID")
    if not app_id:
        return JSONResponse({"error": "OK_APP_ID не найден в .env"}, status_code=400)
    state = secrets.token_urlsafe(16)
    _ok_state_save(state, group_id or "")
    scope = "VALUABLE_ACCESS;LONG_ACCESS_TOKEN;GROUP_CONTENT;PHOTO_CONTENT"
    url = (
        f"https://connect.ok.ru/oauth/authorize"
        f"?client_id={app_id}"
        f"&scope={scope}"
        f"&response_type=code"
        f"&redirect_uri={OK_REDIRECT_URI}"
        f"&state={state}"
        f"&layout=w"
    )
    return RedirectResponse(url)


@app.get("/oauth/ok/callback")
def ok_oauth_callback(code: str = None, error: str = None, state: str = None):
    try:
        if error:
            return RedirectResponse(f"/?ok_error={error}")
        if not code:
            return RedirectResponse("/?ok_error=no_code")
        app_id = os.getenv("OK_APP_ID")
        secret_key = os.getenv("OK_SECRET_KEY")
        group_id = _ok_state_pop(state) if state else ""
        r = http_requests.post(
            "https://api.ok.ru/oauth/token.do",
            params={
                "code": code,
                "redirect_uri": OK_REDIRECT_URI,
                "grant_type": "authorization_code",
                "client_id": app_id,
                "client_secret": secret_key,
            }
        )
        data = r.json()
        if "access_token" not in data:
            err = data.get("error_description") or data.get("error") or str(data)
            return JSONResponse({"ok_token_error": err, "response": data}, status_code=400)
        save_platform("ok", {"access_token": data["access_token"], "group_id": group_id or ""})
        return RedirectResponse("/?ok_connected=1")
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


# ─── Twitter OAuth ───────────────────────────────────────────────
_TWITTER_PKCE_FILE = Path("twitter_pkce.json")


def _twitter_pkce_save(state: str, code_verifier: str):
    data = {}
    if _TWITTER_PKCE_FILE.exists():
        data = json.loads(_TWITTER_PKCE_FILE.read_text())
    data[state] = code_verifier
    _TWITTER_PKCE_FILE.write_text(json.dumps(data))


def _twitter_pkce_pop(state: str):
    if not _TWITTER_PKCE_FILE.exists():
        return None
    data = json.loads(_TWITTER_PKCE_FILE.read_text())
    verifier = data.pop(state, None)
    _TWITTER_PKCE_FILE.write_text(json.dumps(data))
    return verifier


@app.get("/oauth/twitter")
def twitter_oauth_start():
    client_id = os.getenv("TWITTER_CLIENT_ID")
    if not client_id:
        return JSONResponse({"error": "TWITTER_CLIENT_ID не найден в .env"}, status_code=400)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    _twitter_pkce_save(state, code_verifier)
    from urllib.parse import urlencode
    params = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": TWITTER_REDIRECT_URI,
        "scope": "tweet.read tweet.write users.read offline.access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    return RedirectResponse(f"https://x.com/i/oauth2/authorize?{params}")


@app.get("/oauth/twitter/callback")
def twitter_oauth_callback(code: str = None, error: str = None, state: str = None):
    try:
        if error:
            return RedirectResponse(f"/?twitter_error={error}")
        if not code:
            return RedirectResponse("/?twitter_error=no_code")
        client_id = os.getenv("TWITTER_CLIENT_ID")
        client_secret = os.getenv("TWITTER_CLIENT_SECRET")
        code_verifier = _twitter_pkce_pop(state)
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        r = http_requests.post(
            "https://api.twitter.com/2/oauth2/token",
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"code": code, "grant_type": "authorization_code", "redirect_uri": TWITTER_REDIRECT_URI, "code_verifier": code_verifier or ""},
        )
        data = r.json()
        if "access_token" not in data:
            err = data.get("error_description") or data.get("error") or str(data)
            return JSONResponse({"twitter_token_error": err, "response": data}, status_code=400)
        save_platform("twitter", {"access_token": data["access_token"]})
        return RedirectResponse("/?twitter_connected=1")
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


# ─── Facebook OAuth ───────────────────────────────────────────────
_FB_STATE_FILE = Path("fb_state.json")


def _fb_state_save(state: str):
    """Сохраняем state для CSRF-защиты"""
    data = {}
    if _FB_STATE_FILE.exists():
        data = json.loads(_FB_STATE_FILE.read_text())
    data[state] = True
    _FB_STATE_FILE.write_text(json.dumps(data))


def _fb_state_pop(state: str) -> bool:
    """Проверяем и удаляем state"""
    if not _FB_STATE_FILE.exists():
        return False
    data = json.loads(_FB_STATE_FILE.read_text())
    found = data.pop(state, False)
    _FB_STATE_FILE.write_text(json.dumps(data))
    return bool(found)


@app.get("/oauth/facebook")
def facebook_oauth_start():
    """Старт Facebook OAuth — редирект на страницу авторизации"""
    app_id = os.getenv("FB_APP_ID")
    if not app_id:
        return JSONResponse({"error": "FB_APP_ID не найден в .env"}, status_code=400)
    state = secrets.token_urlsafe(16)
    _fb_state_save(state)
    from urllib.parse import urlencode
    params = urlencode({
        "client_id": app_id,
        "redirect_uri": FACEBOOK_REDIRECT_URI,
        "scope": "pages_show_list,pages_manage_posts,pages_read_engagement",
        "response_type": "code",
        "state": state,
    })
    return RedirectResponse(f"https://www.facebook.com/v25.0/dialog/oauth?{params}")


@app.get("/oauth/facebook/callback")
def facebook_oauth_callback(code: str = None, error: str = None, state: str = None):
    """Обработка колбэка от Facebook"""
    try:
        if error:
            return RedirectResponse(f"/?fb_error={error}")
        if not code:
            return RedirectResponse("/?fb_error=no_code")

        # CSRF-проверка state
        if state and not _fb_state_pop(state):
            return RedirectResponse("/?fb_error=invalid_state")

        app_id = os.getenv("FB_APP_ID")
        app_secret = os.getenv("FB_APP_SECRET")

        # Шаг 1: меняем code на краткосрочный User Access Token
        r = http_requests.get("https://graph.facebook.com/v25.0/oauth/access_token", params={
            "client_id": app_id,
            "redirect_uri": FACEBOOK_REDIRECT_URI,
            "client_secret": app_secret,
            "code": code,
        })
        token_data = r.json()
        if "access_token" not in token_data:
            err = token_data.get("error", {}).get("message") or str(token_data)
            return JSONResponse({"fb_token_error": err, "response": token_data}, status_code=400)
        short_token = token_data["access_token"]

        # Шаг 2: меняем на долгоживущий токен (60 дней)
        r2 = http_requests.get("https://graph.facebook.com/v25.0/oauth/access_token", params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        })
        long_token_data = r2.json()
        user_token = long_token_data.get("access_token", short_token)

        # Шаг 3: получаем список страниц пользователя + Page Access Tokens
        r3 = http_requests.get("https://graph.facebook.com/v25.0/me/accounts", params={
            "access_token": user_token,
            "fields": "id,name,access_token,tasks",
        })
        pages_data = r3.json()
        pages = pages_data.get("data", [])

        if not pages:
            return RedirectResponse("/?fb_error=no_pages")

        # Если страница одна — сохраняем сразу
        if len(pages) == 1:
            page = pages[0]
            save_platform("facebook", {
                "page_access_token": page["access_token"],
                "page_id": page["id"],
            })
            return RedirectResponse("/?fb_connected=1")

        # Если несколько страниц — передаём список в URL для выбора в UI
        import urllib.parse
        pages_json = json.dumps([{"id": p["id"], "name": p["name"], "token": p["access_token"]} for p in pages])
        encoded = base64.urlsafe_b64encode(pages_json.encode()).decode()
        return RedirectResponse(f"/?fb_select={urllib.parse.quote(encoded)}")

    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@app.post("/api/facebook/select-page")
async def facebook_select_page(request: Request):
    """Сохранение выбранной страницы Facebook"""
    data = await request.json()
    page_id = data.get("page_id")
    page_token = data.get("page_token")
    if not page_id or not page_token:
        return JSONResponse({"ok": False, "message": "Не указаны page_id или page_token"}, status_code=400)
    save_platform("facebook", {
        "page_access_token": page_token,
        "page_id": page_id,
    })
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
