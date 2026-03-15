from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from typing import List, Optional
import uuid
import shutil
import requests as http_requests
from pathlib import Path
from datetime import datetime

from config import load_credentials, save_platform, clear_platform, get_platform_config

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


def get_poster(platform: str):
    cfg = get_platform_config(platform)
    if not cfg:
        return None
    if platform not in PLATFORM_MAP:
        return None
    module_path, class_name = PLATFORM_MAP[platform]
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**cfg)


def execute_post(platforms: list, text: str, media_path: str = None, media_type: str = None):
    results = {}
    for p in platforms:
        poster = get_poster(p)
        if poster:
            results[p] = poster.post(text, media_path, media_type)
        else:
            results[p] = {"ok": False, "message": "Не настроено"}
    return results


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/status")
def status():
    creds = load_credentials()
    result = {}
    for platform in PLATFORM_MAP:
        result[platform] = "configured" if creds.get(platform) else "not_configured"
    return result


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
    file: Optional[UploadFile] = File(None)
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
    file: Optional[UploadFile] = File(None)
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


VK_REDIRECT_URI = "https://test-connect-production-2101.up.railway.app/oauth/vk/callback"
OK_REDIRECT_URI = "https://test-connect-production-2101.up.railway.app/oauth/ok/callback"
VK_SCOPE = "90116"  # wall(8192) + photos(4) + video(16384) + offline(65536)


_VK_PKCE_FILE = Path("vk_pkce.json")


def _pkce_save(state: str, code_verifier: str):
    import json
    data = {}
    if _VK_PKCE_FILE.exists():
        data = json.loads(_VK_PKCE_FILE.read_text())
    data[state] = code_verifier
    _VK_PKCE_FILE.write_text(json.dumps(data))


def _pkce_pop(state: str):
    import json
    if not _VK_PKCE_FILE.exists():
        return None
    data = json.loads(_VK_PKCE_FILE.read_text())
    verifier = data.pop(state, None)
    _VK_PKCE_FILE.write_text(json.dumps(data))
    return verifier


@app.get("/oauth/vk")
def vk_oauth_start():
    from config import load_credentials
    load_credentials()
    import os, secrets, hashlib, base64
    app_id = os.getenv("VK_APP_ID")
    if not app_id:
        return JSONResponse({"error": "VK_APP_ID не найден в .env"}, status_code=400)

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    _pkce_save(state, code_verifier)

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

        from config import load_credentials
        load_credentials()
        import os
        app_id = os.getenv("VK_APP_ID")
        if not app_id:
            return JSONResponse({"error": "VK_APP_ID не найден"}, status_code=500)

        code_verifier = _pkce_pop(state)

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
            save_platform("vk", {"access_token": data["access_token"]})
            return RedirectResponse("/?vk_connected=1")
        else:
            err = data.get("error_description") or data.get("error") or str(data)
            return JSONResponse({"vk_token_error": err, "response": data}, status_code=400)
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


@app.get("/oauth/ok")
def ok_oauth_start(group_id: str = None):
    import os, secrets
    app_id = os.getenv("OK_APP_ID")
    if not app_id:
        return JSONResponse({"error": "OK_APP_ID не найден в .env"}, status_code=400)

    state = secrets.token_urlsafe(16)
    # Сохраняем group_id вместе со state чтобы использовать после колбэка
    _ok_state_save(state, group_id or "")

    scope = "VALUABLE_ACCESS;LONG_ACCESS_TOKEN;GROUP_CONTENT"
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


_OK_STATE_FILE = Path("ok_state.json")


def _ok_state_save(state: str, group_id: str):
    import json
    data = {}
    if _OK_STATE_FILE.exists():
        data = json.loads(_OK_STATE_FILE.read_text())
    data[state] = group_id
    _OK_STATE_FILE.write_text(json.dumps(data))


def _ok_state_pop(state: str):
    import json
    if not _OK_STATE_FILE.exists():
        return None
    data = json.loads(_OK_STATE_FILE.read_text())
    group_id = data.pop(state, None)
    _OK_STATE_FILE.write_text(json.dumps(data))
    return group_id


@app.get("/oauth/ok/callback")
def ok_oauth_callback(code: str = None, error: str = None, state: str = None):
    try:
        if error:
            return RedirectResponse(f"/?ok_error={error}")
        if not code:
            return RedirectResponse("/?ok_error=no_code")

        import os
        app_id = os.getenv("OK_APP_ID")
        secret_key = os.getenv("OK_SECRET_KEY")
        if not app_id or not secret_key:
            return JSONResponse({"error": "OK_APP_ID или OK_SECRET_KEY не найдены"}, status_code=500)

        group_id = _ok_state_pop(state) if state else ""

        # Обмениваем code на access_token
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

        save_platform("ok", {
            "access_token": data["access_token"],
            "group_id": group_id,
        })
        return RedirectResponse("/?ok_connected=1")
    except Exception as e:
        import traceback
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
