# ROADMAP: Social Networks Auto-Poster

## Стек

- **Backend:** Python + FastAPI
- **Frontend:** Vanilla JS + HTML/CSS (один файл `static/index.html`)
- **Хранилище:** `credentials.json` (токены/ID) + `schedule.json` (задачи)
- **Зависимости:** см. `requirements.txt`

---

## Шаг 0 — Структура проекта и зависимости

**Файлы:**
```
test-connect/
├── SOCIAL_NETWORKS_API.md
├── ROADMAP.md
├── requirements.txt
├── credentials.json          # токены пользователя (gitignore!)
├── schedule.json             # запланированные задачи
├── config.py                 # загрузка credentials.json
├── main.py                   # FastAPI app + все роуты
├── platforms/
│   ├── __init__.py
│   ├── base.py               # абстрактный класс
│   ├── telegram_poster.py
│   ├── vk_poster.py
│   ├── ok_poster.py
│   ├── facebook_poster.py
│   ├── instagram_poster.py
│   ├── twitter_poster.py
│   └── zen_poster.py
├── scheduler.py
├── static/
│   ├── index.html            # весь UI
│   └── rss.xml              # для Яндекс Дзен
└── uploads/                  # временные медиафайлы
```

**requirements.txt:**
```
fastapi
uvicorn[standard]
python-multipart
python-telegram-bot>=21
vk_api
tweepy
requests
apscheduler
feedgen
```

**Действие:** Создать структуру папок, `requirements.txt`, пустые файлы.

```bash
pip install -r requirements.txt
```

---

## Шаг 1 — UI (без бэкенда, только вёрстка)

**Цель:** Полностью сверстать интерфейс с моковыми данными.

### Макет страницы

```
┌─────────────────────────────────────────────────────┐
│  🚀 Social Networks Auto-Poster                     │
├─────────────────────────────────────────────────────┤
│  Сети: [Telegram] [VK] [OK] [Facebook]              │
│        [Instagram] [Twitter] [Дзен]                 │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ Текст сообщения...                           │   │
│  │                                              │   │
│  └──────────────────────────────────────────────┘   │
│  [📎 Фото/Видео]                                    │
│                                                     │
│  [✅ Опубликовать] [🕐 По расписанию]               │
└─────────────────────────────────────────────────────┘

Плитка соцсети:
┌────────────────────┐
│  🔵 Telegram       │
│  ● Подключено      │ ← статус
│                    │
│  [Проверить]       │ ← тест соединения
│  [Подключить]      │ ← открыть форму настроек
│  [Сбросить]        │ ← очистить credentials
└────────────────────┘
```

### Компоненты UI:

1. **Шапка** — название, глобальная кнопка «Опубликовать во все»
2. **Плитки соцсетей** — 7 штук, grid 3-4 колонки
   - Иконка + название
   - Индикатор статуса: `● Подключено` / `○ Не настроено` / `⚠ Ошибка`
   - Кнопки: **[Проверить]**, **[Подключить]**, **[Сбросить]**
3. **Блок публикации** (снизу или справа)
   - Textarea для текста
   - Чекбоксы выбора платформ
   - Upload фото/видео
   - Кнопка **[Опубликовать сейчас]**
   - Кнопка **[По расписанию]** → модалка с датой/временем
4. **Модалка подключения** — форма с полями конкретной соцсети + инструкция
5. **Модалка расписания** — datetime picker + список активных задач

**Результат шага:** Запускается `index.html` как статика, всё кликается, модалки открываются/закрываются, данные хардкодены.

---

## Шаг 2 — Бэкенд: скелет FastAPI

**Цель:** Запускающийся сервер, отдающий UI и базовые роуты.

**Файл `config.py`:**
```python
import json, os
from pathlib import Path

CREDENTIALS_FILE = Path("credentials.json")
SCHEDULE_FILE = Path("schedule.json")

def load_credentials() -> dict:
    if CREDENTIALS_FILE.exists():
        return json.loads(CREDENTIALS_FILE.read_text())
    return {}

def save_credentials(data: dict):
    CREDENTIALS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def get_platform_config(platform: str) -> dict:
    return load_credentials().get(platform, {})
```

**Роуты `main.py`:**
```
GET  /                          → static/index.html
GET  /api/status                → статус всех платформ (connected/not_configured/error)
POST /api/connect/{platform}    → сохранить credentials в json
DELETE /api/connect/{platform}  → сбросить credentials
POST /api/test/{platform}       → тест соединения
POST /api/post                  → опубликовать (text, platforms[], file?)
POST /api/schedule              → запланировать
GET  /api/jobs                  → список задач
DELETE /api/jobs/{job_id}       → отмена
```

**Файл `credentials.json` (структура):**
```json
{
  "telegram": {
    "bot_token": "...",
    "chat_id": "..."
  },
  "vk": {
    "access_token": "...",
    "owner_id": "..."
  },
  "ok": {
    "access_token": "...",
    "session_secret_key": "...",
    "application_key": "...",
    "secret_key": "...",
    "group_id": "..."
  },
  "facebook": {
    "page_access_token": "...",
    "page_id": "..."
  },
  "instagram": {
    "access_token": "...",
    "user_id": "..."
  },
  "twitter": {
    "api_key": "...",
    "api_secret": "...",
    "access_token": "...",
    "access_token_secret": "..."
  },
  "zen": {
    "feed_title": "...",
    "author_name": "..."
  }
}
```

**Файл `platforms/base.py`:**
```python
from abc import ABC, abstractmethod

class BasePlatform(ABC):
    @abstractmethod
    def test_connection(self) -> dict:
        # возвращает {"ok": True/False, "message": "..."}
        ...

    @abstractmethod
    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        # возвращает {"ok": True/False, "post_id": "...", "message": "..."}
        ...
```

**Результат шага:** `uvicorn main:app --reload` поднимает сервер, UI грузится, JS делает fetch к `/api/status` и получает JSON.

---

## Шаг 3 — Telegram

**Форма подключения (в модалке):**
- `Bot Token` (обязательно)
- `Chat ID` (обязательно)
- Инструкция: «1. Найди @BotFather → /newbot → скопируй токен. 2. Добавь бота в канал как admin. 3. Перешли сообщение из канала в @userinfobot → получи chat_id.»

**Файл `platforms/telegram_poster.py`:**
```python
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from .base import BasePlatform

class TelegramPoster(BasePlatform):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    def test_connection(self) -> dict:
        try:
            info = asyncio.run(self.bot.get_me())
            return {"ok": True, "message": f"Бот @{info.username} подключён"}
        except TelegramError as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            if media_path and media_type == "photo":
                with open(media_path, "rb") as f:
                    msg = asyncio.run(self.bot.send_photo(self.chat_id, photo=f, caption=text))
            elif media_path and media_type == "video":
                with open(media_path, "rb") as f:
                    msg = asyncio.run(self.bot.send_video(self.chat_id, video=f, caption=text))
            else:
                msg = asyncio.run(self.bot.send_message(self.chat_id, text=text))
            return {"ok": True, "post_id": str(msg.message_id)}
        except TelegramError as e:
            return {"ok": False, "message": str(e)}
```

**Проверка:**
1. Открыть UI → плитка Telegram → [Подключить]
2. Ввести токен и chat_id → [Сохранить]
3. [Проверить] → должен показать «Бот @username подключён»
4. Ввести текст → выбрать Telegram → [Опубликовать сейчас] → проверить в Telegram

---

## Шаг 4 — VK

**Приложение создаётся на:** https://id.vk.com/about/business/go/accounts — тип Standalone.

**Переменные окружения:**
- `VK_APP_ID` — ID приложения (из URL настроек)
- `VK_CLIENT_SECRET` — Защищённый ключ из настроек приложения
- `VK_ACCESS_TOKEN` — токен пользователя (получается через OAuth flow)
- `VK_TARGET_ID` — ID группы/паблика куда постить (отрицательное число, например `-123456789`)

**OAuth flow:**
1. В настройках приложения: Доверенный Redirect URL → `http://localhost/oauth/vk/callback`
2. Приложение запускается на порту 80 (`sudo python run.py`)
3. Пользователь нажимает «Подключить VK» → редирект на VK auth → VK возвращает `code`
4. `GET /oauth/vk/callback?code=...` → меняем code на access_token → сохраняем в `.env`

**OAuth роуты в `main.py`:**
```
GET /oauth/vk          → редирект на https://oauth.vk.com/authorize?...&scope=wall,photos,offline
GET /oauth/vk/callback → принимает code, меняет на token через https://oauth.vk.com/access_token
```

**Форма подключения (в модалке UI):**
- Кнопка «Подключить через VK» (запускает OAuth)
- `ID группы/паблика` — куда постить (например `-123456789` для группы)
- Инструкция: «ID группы — отрицательное число. Найти: открыть страницу группы → в URL club123456 → ID = -123456»

**Файл `platforms/vk_poster.py`:**
```python
import vk_api
from .base import BasePlatform

class VKPoster(BasePlatform):
    def __init__(self, access_token: str, target_id: str, app_id: str = None, client_secret: str = None):
        self.session = vk_api.VkApi(token=access_token)
        self.vk = self.session.get_api()
        self.owner_id = int(target_id)

    def test_connection(self) -> dict:
        try:
            info = self.vk.users.get()
            user = info[0]
            return {"ok": True, "message": f"Подключён как {user['first_name']} {user['last_name']}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            attachments = []
            if media_path and media_type == "photo":
                upload = vk_api.VkUpload(self.session)
                photo = upload.photo_wall(media_path, group_id=abs(self.owner_id))
                p = photo[0]
                attachments.append(f"photo{p['owner_id']}_{p['id']}")
            result = self.vk.wall.post(
                owner_id=self.owner_id,
                message=text,
                attachments=",".join(attachments)
            )
            return {"ok": True, "post_id": str(result["post_id"])}
        except Exception as e:
            return {"ok": False, "message": str(e)}
```

**Проверка:** аналогично Telegram.

---

## Шаг 5 — Одноклассники (OK.ru)

**Форма подключения:**
- `Access Token`
- `Session Secret Key`
- `Application Key` (public key)
- `Secret Key`
- `Group ID` (без знака)
- Инструкция: ссылка на ok.ru/vitrine/myuploaded → «Вечный access_token»

**Файл `platforms/ok_poster.py`:**
```python
import hashlib, requests
from .base import BasePlatform

class OKPoster(BasePlatform):
    BASE = "https://api.ok.ru/fb.do"

    def __init__(self, access_token, session_secret_key, application_key, secret_key, group_id):
        self.access_token = access_token
        self.session_secret_key = session_secret_key
        self.application_key = application_key
        self.secret_key = secret_key
        self.group_id = group_id

    def _sig(self, params: dict) -> str:
        # sig = MD5(sorted_params_string + MD5(access_token + secret_key))
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
            import json
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
```

---

## Шаг 6 — Facebook Pages

**Форма подключения:**
- `Page Access Token`
- `Page ID`
- Инструкция: Graph Explorer → /me/accounts → скопировать access_token и id

**Файл `platforms/facebook_poster.py`:**
```python
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
```

---

## Шаг 7 — Instagram Graph API

**Форма подключения:**
- `Access Token` (Page Access Token, тот же что Facebook)
- `Instagram User ID`
- Инструкция: GET /{page-id}?fields=instagram_business_account → получить id
- Предупреждение: медиа должно быть по публичному HTTPS URL

**Файл `platforms/instagram_poster.py`:**
```python
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
        # Instagram требует публичный URL для медиа — без него только текст через карусель не работает
        # Для теста — пост без медиа не поддерживается IG API, нужна image_url
        try:
            if not media_path:
                return {"ok": False, "message": "Instagram требует медиафайл (публичный URL)"}
            # Шаг 1: создать контейнер (image_url должен быть публичным HTTPS)
            # В реальном использовании media_path должен быть URL
            r = requests.post(f"{self.BASE}/{self.user_id}/media", data={
                "image_url": media_path,  # должен быть публичный URL
                "caption": text,
                "access_token": self.token
            })
            data = r.json()
            if "error" in data:
                return {"ok": False, "message": data["error"]["message"]}
            creation_id = data["id"]
            # Шаг 2: опубликовать
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
```

---

## Шаг 8 — X (Twitter)

**Форма подключения:**
- `API Key`
- `API Secret`
- `Access Token`
- `Access Token Secret`
- Инструкция: developer.x.com → App → Keys and Tokens → сохранить при создании!

**Файл `platforms/twitter_poster.py`:**
```python
import tweepy
from .base import BasePlatform

class TwitterPoster(BasePlatform):
    def __init__(self, api_key, api_secret, access_token, access_token_secret):
        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )

    def test_connection(self) -> dict:
        try:
            me = self.client.get_me()
            return {"ok": True, "message": f"Twitter: @{me.data.username}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            tweet = self.client.create_tweet(text=text)
            return {"ok": True, "post_id": str(tweet.data["id"])}
        except Exception as e:
            return {"ok": False, "message": str(e)}
```

---

## Шаг 9 — Яндекс Дзен (RSS)

**Форма подключения:**
- `Название канала`
- `Имя автора`
- Инструкция: Дзен Studio → Настройки → Импорт из RSS → указать `http://your-server/static/rss.xml`

**Файл `platforms/zen_poster.py`:**
```python
import json
from pathlib import Path
from datetime import datetime
from feedgen.feed import FeedGenerator
from .base import BasePlatform

RSS_FILE = Path("static/rss.xml")
ZEN_POSTS_FILE = Path("zen_posts.json")

class ZenPoster(BasePlatform):
    def __init__(self, feed_title: str, author_name: str, base_url: str = "http://localhost:8000"):
        self.feed_title = feed_title
        self.author_name = author_name
        self.base_url = base_url

    def _load_posts(self) -> list:
        if ZEN_POSTS_FILE.exists():
            return json.loads(ZEN_POSTS_FILE.read_text())
        return []

    def _save_posts(self, posts: list):
        ZEN_POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2))

    def _regenerate_rss(self, posts: list):
        fg = FeedGenerator()
        fg.id(f"{self.base_url}/static/rss.xml")
        fg.title(self.feed_title)
        fg.author({"name": self.author_name})
        fg.link(href=f"{self.base_url}/static/rss.xml", rel="self")
        for post in posts[-50:]:  # последние 50
            fe = fg.add_entry()
            fe.id(post["id"])
            fe.title(post["title"])
            fe.content(post["content"], type="html")
            fe.published(post["published"])
        fg.rss_file(str(RSS_FILE))

    def test_connection(self) -> dict:
        return {"ok": True, "message": f"RSS готов: {self.base_url}/static/rss.xml"}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            posts = self._load_posts()
            post_id = f"post-{len(posts)+1}-{int(datetime.now().timestamp())}"
            title = text[:80] + ("..." if len(text) > 80 else "")
            posts.append({
                "id": f"{self.base_url}/{post_id}",
                "title": title,
                "content": f"<p>{text}</p>",
                "published": datetime.now().isoformat() + "Z"
            })
            self._save_posts(posts)
            self._regenerate_rss(posts)
            return {"ok": True, "post_id": post_id, "message": "Добавлено в RSS"}
        except Exception as e:
            return {"ok": False, "message": str(e)}
```

---

## Шаг 10 — Планировщик

**Файл `scheduler.py`:**
```python
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import json
from pathlib import Path

SCHEDULE_FILE = Path("schedule.json")
scheduler = BackgroundScheduler()
scheduler.start()

def _load_jobs() -> list:
    if SCHEDULE_FILE.exists():
        return json.loads(SCHEDULE_FILE.read_text())
    return []

def _save_jobs(jobs: list):
    SCHEDULE_FILE.write_text(json.dumps(jobs, ensure_ascii=False, indent=2))

def schedule_post(job_id: str, run_at: datetime, platforms: list, text: str, media_path: str = None):
    from main import execute_post  # импорт здесь чтобы избежать циклического
    def job():
        execute_post(platforms, text, media_path)
        # убрать из списка после выполнения
        jobs = [j for j in _load_jobs() if j["id"] != job_id]
        _save_jobs(jobs)

    scheduler.add_job(job, "date", run_date=run_at, id=job_id)
    jobs = _load_jobs()
    jobs.append({
        "id": job_id,
        "run_at": run_at.isoformat(),
        "platforms": platforms,
        "text": text[:100],
        "status": "pending"
    })
    _save_jobs(jobs)

def cancel_job(job_id: str) -> bool:
    try:
        scheduler.remove_job(job_id)
        jobs = [j for j in _load_jobs() if j["id"] != job_id]
        _save_jobs(jobs)
        return True
    except Exception:
        return False

def list_jobs() -> list:
    return _load_jobs()
```

---

## Шаг 11 — Интеграция в main.py

**Полная схема `main.py`:**
```python
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional
import uuid, shutil
from pathlib import Path
from config import load_credentials, save_credentials, get_platform_config
from platforms.telegram_poster import TelegramPoster
from platforms.vk_poster import VKPoster
# ... остальные импорты

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

PLATFORM_MAP = {
    "telegram": TelegramPoster,
    "vk": VKPoster,
    "ok": OKPoster,
    "facebook": FacebookPoster,
    "instagram": InstagramPoster,
    "twitter": TwitterPoster,
    "zen": ZenPoster,
}

def get_poster(platform: str):
    cfg = get_platform_config(platform)
    if not cfg:
        return None
    cls = PLATFORM_MAP[platform]
    return cls(**cfg)

def execute_post(platforms: list, text: str, media_path: str = None):
    results = {}
    for p in platforms:
        poster = get_poster(p)
        if poster:
            results[p] = poster.post(text, media_path)
        else:
            results[p] = {"ok": False, "message": "Не настроено"}
    return results

@app.get("/")
def index(): return FileResponse("static/index.html")

@app.get("/api/status")
def status():
    creds = load_credentials()
    result = {}
    for platform in PLATFORM_MAP:
        result[platform] = "configured" if creds.get(platform) else "not_configured"
    return result

@app.post("/api/connect/{platform}")
def connect(platform: str, data: dict):
    creds = load_credentials()
    creds[platform] = data
    save_credentials(creds)
    return {"ok": True}

@app.delete("/api/connect/{platform}")
def disconnect(platform: str):
    creds = load_credentials()
    creds.pop(platform, None)
    save_credentials(creds)
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
    if file:
        Path("uploads").mkdir(exist_ok=True)
        media_path = f"uploads/{uuid.uuid4()}_{file.filename}"
        with open(media_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    return execute_post(platforms, text, media_path)

@app.post("/api/schedule")
async def schedule(
    text: str = Form(...),
    platforms: List[str] = Form(...),
    run_at: str = Form(...),  # ISO datetime
    file: Optional[UploadFile] = File(None)
):
    from scheduler import schedule_post
    from datetime import datetime
    media_path = None
    if file:
        Path("uploads").mkdir(exist_ok=True)
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
```

---

## Шаг 12 — Финальное тестирование

### Чеклист:

- [ ] `sudo python run.py` — сервер стартует без ошибок на порту 80
- [ ] Открыть `http://localhost` — UI отображается
- [ ] `/api/status` — возвращает `not_configured` для всех
- [ ] Подключить Telegram → `/api/test/telegram` → `{"ok": true}`
- [ ] Опубликовать в Telegram через UI — сообщение пришло
- [ ] Подключить VK → тест → пост
- [ ] Подключить OK → тест → пост
- [ ] Подключить Facebook → тест → пост
- [ ] Подключить Instagram → тест (для поста нужен публичный URL медиа)
- [ ] Подключить Twitter → тест → пост
- [ ] Zen → пост → RSS-файл обновился → доступен по URL
- [ ] Запланировать пост → появляется в `/api/jobs` → срабатывает в нужное время
- [ ] Отмена задачи → удаляется из списка

---

## Порядок реализации (приоритеты)

| # | Шаг | Что даёт |
|---|-----|----------|
| 0 | Структура + deps | Скелет проекта |
| 1 | UI | Визуальная основа |
| 2 | FastAPI скелет | Рабочий сервер + API |
| 3 | Telegram | Первая работающая платформа |
| 4 | VK | Вторая платформа |
| 5 | OK.ru | Третья |
| 6 | Facebook | Четвёртая |
| 7 | Instagram | Пятая (зависит от FB) |
| 8 | Twitter | Шестая |
| 9 | Zen RSS | Седьмая |
| 10 | Планировщик | Отложенный постинг |
| 11 | Интеграция | Всё вместе |
| 12 | Финальное QA | Готово к использованию |
