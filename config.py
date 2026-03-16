import json
from database import get_db


def get_platform_config(platform: str, user_id: int) -> dict:
    """Возвращает конфиг платформы для конкретного пользователя."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT data FROM credentials WHERE user_id=? AND platform=?",
            (user_id, platform),
        ).fetchone()
        return json.loads(row["data"]) if row else {}


def save_platform(platform: str, cfg: dict, user_id: int):
    """Сохраняет или обновляет конфиг платформы для пользователя."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO credentials (user_id, platform, data) VALUES (?,?,?) "
            "ON CONFLICT(user_id, platform) DO UPDATE SET data=excluded.data",
            (user_id, platform, json.dumps(cfg)),
        )


def clear_platform(platform: str, user_id: int):
    """Удаляет конфиг платформы для пользователя."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM credentials WHERE user_id=? AND platform=?",
            (user_id, platform),
        )


def load_credentials(user_id: int) -> dict:
    """Загружает все платформы пользователя."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT platform, data FROM credentials WHERE user_id=?",
            (user_id,),
        ).fetchall()
        return {row["platform"]: json.loads(row["data"]) for row in rows}
