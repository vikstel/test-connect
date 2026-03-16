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
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, Cookie, Depends
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import requests as http_requests

from database import init_db, get_db
from auth import hash_password, verify_password, create_token, decode_token
from config import load_credentials, save_platform, clear_platform, get_platform_config

# Загружаем .env для app-level переменных (VK_APP_ID, OK_APP_ID и т.д.)
load_dotenv(override=True)

app = FastAPI()

Path("uploads").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Инициализируем БД при старте
init_db()


# ─── Redirect URIs ───────────────────────────────────────────────
VK_REDIRECT_URI = "https://test-connect-production-2101.up.railway.app/oauth/vk/callback"
OK_REDIRECT_URI = "https://test-connect-production-2101.up.railway.app/oauth/ok/callback"
TWITTER_REDIRECT_URI = "https://test-connect-production-2101.up.railway.app/oauth/twitter/callback"
VK_SCOPE = "90116"  # wall(8192) + photos(4) + video(16384) + offline(65536)


# ─── Platform map ────────────────────────────────────────────────
PLATFORM_MAP = {
    "telegram": ("platforms.telegram_poster", "TelegramPoster"),
    "vk": ("platforms.vk_poster", "VKPoster"),
    "ok": ("platforms.ok_poster", "OKPoster"),
    "facebook": ("platforms.facebook_poster", "FacebookPoster"),
    "instagram": ("platforms.instagram_poster", "InstagramPoster"),
    "twitter": ("platforms.twitter_poster", "TwitterPoster"),
    "zen": ("platforms.zen_poster", "ZenPoster"),
}


# ─── Auth dependency ─────────────────────────────────────────────
def get_current_user_id(access_token: str = Cookie(None)) -> int:
    """FastAPI dependency: извлекает user_id из JWT cookie."""
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(access_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload["user_id"]


def get_optional_user_id(access_token: str = Cookie(None)) -> int | None:
    """Возвращает user_id или None (для OAuth callbacks без dependency)."""
    if not access_token:
        return None
    payload = decode_token(access_token)
    return payload["user_id"] if payload else None


# ─── Helpers ─────────────────────────────────────────────────────
def get_poster(platform: str, user_id: int):
    cfg = get_platform_config(platform, user_id)
    if not cfg:
        return None
    if platform not in PLATFORM_MAP:
        return None
    module_path, class_name = PLATFORM_MAP[platform]
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**cfg)


def execute_post(platforms: list, text: str, user_id: int, media_path: str = None, media_type: str = None):
    results = {}
    for p in platforms:
        poster = get_poster(p, user_id)
        if poster:
            results[p] = poster.post(text, media_path, media_type)
        else:
            results[p] = {"ok": False, "message": "Не настроено"}
    return results


# ─── Static & Auth routes ────────────────────────────────────────
@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/api/auth/register")
async def register(request: Request):
    data = await request.json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return JSONResponse({"ok": False, "message": "Email и пароль обязательны"}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"ok": False, "message": "Пароль минимум 6 символов"}, status_code=400)
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?) RETURNING id",
                (email, hash_password(password)),
            )
            user_id = cursor.fetchone()["id"]
        token = create_token(user_id)
        response = JSONResponse({"ok": True, "email": email})
        response.set_cookie("access_token", token, httponly=True, max_age=86400 * 30, samesite="lax")
        return response
    except Exception as e:
        if "UNIQUE" in str(e):
            return JSONResponse({"ok": False, "message": "Email уже зарегистрирован"}, status_code=400)
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@app.post("/api/auth/login")
async def login(request: Request):
    data = await request.json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return JSONResponse({"ok": False, "message": "Неверный email или пароль"}, status_code=401)
    token = create_token(row["id"])
    response = JSONResponse({"ok": True, "email": email})
    response.set_cookie("access_token", token, httponly=True, max_age=86400 * 30, samesite="lax")
    return response


@app.post("/api/auth/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("access_token")
    return response


@app.get("/api/auth/me")
def me(user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        row = conn.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(401)
    return {"user_id": user_id, "email": row["email"]}


# ─── Platform API ────────────────────────────────────────────────
@app.get("/api/status")
def status(user_id: int = Depends(get_current_user_id)):
    creds = load_credentials(user_id)
    return {platform: ("configured" if creds.get(platform) else "not_configured") for platform in PLATFORM_MAP}


@app.post("/api/connect/{platform}")
async def connect(platform: str, request: Request, user_id: int = Depends(get_current_user_id)):
    data = await request.json()
    save_platform(platform, data, user_id)
    return {"ok": True}


@app.delete("/api/connect/{platform}")
def disconnect(platform: str, user_id: int = Depends(get_current_user_id)):
    clear_platform(platform, user_id)
    return {"ok": True}


@app.post("/api/test/{platform}")
def test_platform(platform: str, user_id: int = Depends(get_current_user_id)):
    poster = get_poster(platform, user_id)
    if not poster:
        return {"ok": False, "message": "Платформа не настроена"}
    return poster.test_connection()


@app.post("/api/post")
async def post_now(
    text: str = Form(...),
    platforms: List[str] = Form(...),
    file: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
):
    media_path = None
    media_type = None
    if file and file.filename:
        media_path = f"uploads/{uuid.uuid4()}_{file.filename}"
        with open(media_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        ext = file.filename.rsplit(".", 1)[-1].lower()
        media_type = "video" if ext in ("mp4", "mov", "avi", "mkv") else "photo"
    return execute_post(platforms, text, user_id, media_path, media_type)


@app.post("/api/schedule")
async def schedule(
    text: str = Form(...),
    platforms: List[str] = Form(...),
    run_at: str = Form(...),
    file: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
):
    from scheduler import schedule_post
    media_path = None
    if file and file.filename:
        media_path = f"uploads/{uuid.uuid4()}_{file.filename}"
        with open(media_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    job_id = str(uuid.uuid4())
    schedule_post(job_id, datetime.fromisoformat(run_at), platforms, text, user_id, media_path)
    return {"ok": True, "job_id": job_id}


@app.get("/api/jobs")
def get_jobs(user_id: int = Depends(get_current_user_id)):
    from scheduler import list_jobs
    return list_jobs(user_id)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, user_id: int = Depends(get_current_user_id)):
    from scheduler import cancel_job
    return {"ok": cancel_job(job_id, user_id)}


# ─── VK OAuth ────────────────────────────────────────────────────
_VK_PKCE_FILE = Path("vk_pkce.json")


def _pkce_save(state: str, code_verifier: str, user_id: int):
    data = {}
    if _VK_PKCE_FILE.exists():
        data = json.loads(_VK_PKCE_FILE.read_text())
    data[state] = {"verifier": code_verifier, "user_id": user_id}
    _VK_PKCE_FILE.write_text(json.dumps(data))


def _pkce_pop(state: str):
    if not _VK_PKCE_FILE.exists():
        return None, None
    data = json.loads(_VK_PKCE_FILE.read_text())
    entry = data.pop(state, None)
    _VK_PKCE_FILE.write_text(json.dumps(data))
    if not entry:
        return None, None
    return entry.get("verifier"), entry.get("user_id")


@app.get("/oauth/vk")
def vk_oauth_start(user_id: int = Depends(get_current_user_id)):
    app_id = os.getenv("VK_APP_ID")
    if not app_id:
        return JSONResponse({"error": "VK_APP_ID не найден в .env"}, status_code=400)

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    _pkce_save(state, code_verifier, user_id)

    url = (
        f"https://id.vk.ru/authorize"
        f"?client_id={app_id}"
        f"&redirect_uri={VK_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={VK_SCOPE}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )
    return RedirectResponse(url)


@app.get("/oauth/vk/callback")
def vk_oauth_callback(
    code: str = None, error: str = None, error_description: str = None,
    state: str = None, device_id: str = None
):
    try:
        if error:
            return RedirectResponse(f"/?vk_error={error_description or error}")
        if not code:
            return RedirectResponse("/?vk_error=no_code")

        app_id = os.getenv("VK_APP_ID")
        if not app_id:
            return JSONResponse({"error": "VK_APP_ID не найден"}, status_code=500)

        code_verifier, user_id = _pkce_pop(state)
        if not user_id:
            return RedirectResponse("/?vk_error=session_expired")

        query_params = {
            "grant_type": "authorization_code",
            "redirect_uri": VK_REDIRECT_URI,
            "client_id": app_id,
            "device_id": device_id,
            "state": state,
        }
        if code_verifier:
            query_params["code_verifier"] = code_verifier

        r = http_requests.post(
            "https://id.vk.ru/oauth2/auth",
            params=query_params,
            data={"code": code},
        )
        data = r.json()

        if "access_token" in data:
            save_platform("vk", {"access_token": data["access_token"]}, user_id)
            return RedirectResponse("/?vk_connected=1")
        else:
            err = data.get("error_description") or data.get("error") or str(data)
            return JSONResponse({"vk_token_error": err, "response": data}, status_code=400)
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


# ─── OK OAuth ────────────────────────────────────────────────────
_OK_STATE_FILE = Path("ok_state.json")


def _ok_state_save(state: str, group_id: str, user_id: int):
    data = {}
    if _OK_STATE_FILE.exists():
        data = json.loads(_OK_STATE_FILE.read_text())
    data[state] = {"group_id": group_id, "user_id": user_id}
    _OK_STATE_FILE.write_text(json.dumps(data))


def _ok_state_pop(state: str):
    if not _OK_STATE_FILE.exists():
        return None, None
    data = json.loads(_OK_STATE_FILE.read_text())
    entry = data.pop(state, None)
    _OK_STATE_FILE.write_text(json.dumps(data))
    if not entry:
        return None, None
    return entry.get("group_id", ""), entry.get("user_id")


@app.get("/oauth/ok")
def ok_oauth_start(group_id: str = None, user_id: int = Depends(get_current_user_id)):
    app_id = os.getenv("OK_APP_ID")
    if not app_id:
        return JSONResponse({"error": "OK_APP_ID не найден в .env"}, status_code=400)

    state = secrets.token_urlsafe(16)
    _ok_state_save(state, group_id or "", user_id)

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
        if not app_id or not secret_key:
            return JSONResponse({"error": "OK_APP_ID или OK_SECRET_KEY не найдены"}, status_code=500)

        group_id, user_id = _ok_state_pop(state) if state else (None, None)
        if not user_id:
            return RedirectResponse("/?ok_error=session_expired")

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

        save_platform("ok", {"access_token": data["access_token"], "group_id": group_id or ""}, user_id)
        return RedirectResponse("/?ok_connected=1")
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


# ─── Twitter OAuth ───────────────────────────────────────────────
_TWITTER_PKCE_FILE = Path("twitter_pkce.json")


def _twitter_pkce_save(state: str, code_verifier: str, user_id: int):
    data = {}
    if _TWITTER_PKCE_FILE.exists():
        data = json.loads(_TWITTER_PKCE_FILE.read_text())
    data[state] = {"verifier": code_verifier, "user_id": user_id}
    _TWITTER_PKCE_FILE.write_text(json.dumps(data))


def _twitter_pkce_pop(state: str):
    if not _TWITTER_PKCE_FILE.exists():
        return None, None
    data = json.loads(_TWITTER_PKCE_FILE.read_text())
    entry = data.pop(state, None)
    _TWITTER_PKCE_FILE.write_text(json.dumps(data))
    if not entry:
        return None, None
    return entry.get("verifier"), entry.get("user_id")


@app.get("/oauth/twitter")
def twitter_oauth_start(user_id: int = Depends(get_current_user_id)):
    client_id = os.getenv("TWITTER_CLIENT_ID")
    if not client_id:
        return JSONResponse({"error": "TWITTER_CLIENT_ID не найден в .env"}, status_code=400)

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    _twitter_pkce_save(state, code_verifier, user_id)

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
    return RedirectResponse(f"https://twitter.com/i/oauth2/authorize?{params}")


@app.get("/oauth/twitter/callback")
def twitter_oauth_callback(code: str = None, error: str = None, state: str = None):
    try:
        if error:
            return RedirectResponse(f"/?twitter_error={error}")
        if not code:
            return RedirectResponse("/?twitter_error=no_code")

        client_id = os.getenv("TWITTER_CLIENT_ID")
        client_secret = os.getenv("TWITTER_CLIENT_SECRET")
        if not client_id or not client_secret:
            return JSONResponse({"error": "TWITTER_CLIENT_ID или TWITTER_CLIENT_SECRET не найдены"}, status_code=500)

        code_verifier, user_id = _twitter_pkce_pop(state)
        if not user_id:
            return RedirectResponse("/?twitter_error=session_expired")

        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        r = http_requests.post(
            "https://api.twitter.com/2/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": TWITTER_REDIRECT_URI,
                "code_verifier": code_verifier or "",
            },
        )
        data = r.json()

        if "access_token" not in data:
            err = data.get("error_description") or data.get("error") or str(data)
            return JSONResponse({"twitter_token_error": err, "response": data}, status_code=400)

        save_platform("twitter", {"access_token": data["access_token"]}, user_id)
        return RedirectResponse("/?twitter_connected=1")
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
