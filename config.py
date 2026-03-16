import json
from pathlib import Path

CREDENTIALS_FILE = Path("credentials.json")


def load_credentials() -> dict:
    if CREDENTIALS_FILE.exists():
        return json.loads(CREDENTIALS_FILE.read_text())
    return {}


def save_platform(platform: str, cfg: dict):
    creds = load_credentials()
    creds[platform] = cfg
    CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2, ensure_ascii=False))


def clear_platform(platform: str):
    creds = load_credentials()
    creds.pop(platform, None)
    CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2, ensure_ascii=False))


def get_platform_config(platform: str) -> dict:
    return load_credentials().get(platform, {})
