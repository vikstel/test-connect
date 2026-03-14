import os
from pathlib import Path
from dotenv import load_dotenv, set_key, unset_key

ENV_FILE = Path(".env")
SCHEDULE_FILE = Path("schedule.json")

# Mapping: platform -> {field_name -> ENV_KEY}
PLATFORM_ENV_KEYS = {
    "telegram": {
        "bot_token": "TELEGRAM_BOT_TOKEN",
        "chat_id": "TELEGRAM_CHAT_ID",
    },
    "vk": {
        "access_token": "VK_ACCESS_TOKEN",
        "owner_id": "VK_OWNER_ID",
    },
    "ok": {
        "access_token": "OK_ACCESS_TOKEN",
        "session_secret_key": "OK_SESSION_SECRET_KEY",
        "application_key": "OK_APPLICATION_KEY",
        "secret_key": "OK_SECRET_KEY",
        "group_id": "OK_GROUP_ID",
    },
    "facebook": {
        "page_access_token": "FACEBOOK_PAGE_ACCESS_TOKEN",
        "page_id": "FACEBOOK_PAGE_ID",
    },
    "instagram": {
        "access_token": "INSTAGRAM_ACCESS_TOKEN",
        "user_id": "INSTAGRAM_USER_ID",
    },
    "twitter": {
        "api_key": "TWITTER_API_KEY",
        "api_secret": "TWITTER_API_SECRET",
        "access_token": "TWITTER_ACCESS_TOKEN",
        "access_token_secret": "TWITTER_ACCESS_TOKEN_SECRET",
    },
    "zen": {
        "feed_title": "ZEN_FEED_TITLE",
        "author_name": "ZEN_AUTHOR_NAME",
    },
}


def _ensure_env_file():
    if not ENV_FILE.exists():
        ENV_FILE.write_text("")


def load_credentials() -> dict:
    _ensure_env_file()
    load_dotenv(ENV_FILE, override=True)
    result = {}
    for platform, keys in PLATFORM_ENV_KEYS.items():
        cfg = {}
        for field, env_key in keys.items():
            val = os.getenv(env_key)
            if val:
                cfg[field] = val
        if cfg:
            result[platform] = cfg
    return result


def save_credentials(data: dict):
    """data = full credentials dict (all platforms)"""
    _ensure_env_file()
    # Write only the platforms present in data; clear removed ones
    for platform, keys in PLATFORM_ENV_KEYS.items():
        cfg = data.get(platform, {})
        for field, env_key in keys.items():
            if cfg.get(field):
                set_key(str(ENV_FILE), env_key, cfg[field])
            else:
                unset_key(str(ENV_FILE), env_key)


def save_platform(platform: str, cfg: dict):
    """Save a single platform config."""
    _ensure_env_file()
    keys = PLATFORM_ENV_KEYS.get(platform, {})
    for field, env_key in keys.items():
        if cfg.get(field):
            set_key(str(ENV_FILE), env_key, cfg[field])


def clear_platform(platform: str):
    """Remove all keys for a platform."""
    _ensure_env_file()
    keys = PLATFORM_ENV_KEYS.get(platform, {})
    for env_key in keys.values():
        unset_key(str(ENV_FILE), env_key)


def get_platform_config(platform: str) -> dict:
    load_dotenv(ENV_FILE, override=True)
    keys = PLATFORM_ENV_KEYS.get(platform, {})
    cfg = {}
    for field, env_key in keys.items():
        val = os.getenv(env_key)
        if val:
            cfg[field] = val
    return cfg
