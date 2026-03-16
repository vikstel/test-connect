import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path("data.db")


def init_db():
    """Создаёт таблицы при первом запуске."""
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                data TEXT NOT NULL,
                UNIQUE(user_id, platform),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        conn.commit()


@contextmanager
def get_db():
    """Контекстный менеджер для SQLite соединения."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
