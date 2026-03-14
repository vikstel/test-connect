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


VK_REDIRECT_URI = "http://localhost/oauth/vk/callback"
VK_SCOPE = "wall,photos,video,offline"


@app.get("/oauth/vk")
def vk_oauth_start():
    from config import load_credentials
    load_credentials()
    import os
    app_id = os.getenv("VK_APP_ID")
    if not app_id:
        return JSONResponse({"error": "VK_APP_ID не найден в .env"}, status_code=400)
    url = (
        f"https://oauth.vk.com/authorize"
        f"?client_id={app_id}"
        f"&display=page"
        f"&redirect_uri={VK_REDIRECT_URI}"
        f"&scope={VK_SCOPE}"
        f"&response_type=token"
        f"&v=5.199"
    )
    return RedirectResponse(url)


@app.get("/oauth/vk/callback")
def vk_oauth_callback():
    # Token arrives in URL fragment (#access_token=...) — handled by JS on this page
    html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>VK Auth</title></head>
<body>
<script>
  const hash = location.hash.substring(1);
  const params = Object.fromEntries(new URLSearchParams(hash));
  if (params.access_token) {
    fetch('/api/vk/save_token', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({access_token: params.access_token})
    }).then(() => { window.location.href = '/?vk_connected=1'; });
  } else {
    const err = params.error_description || params.error || 'unknown';
    window.location.href = '/?vk_error=' + encodeURIComponent(err);
  }
</script>
<p>Авторизация VK...</p>
</body></html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


@app.post("/api/vk/save_token")
async def vk_save_token(request: Request):
    data = await request.json()
    token = data.get("access_token")
    if not token:
        return {"ok": False}
    save_platform("vk", {"access_token": token})
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
