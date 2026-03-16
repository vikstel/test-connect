import os
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-change-in-prod-please")
ALGORITHM = "HS256"
EXPIRE_DAYS = 30

# Контекст для bcrypt хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_token(user_id: int) -> str:
    """Создаёт JWT токен для пользователя."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Декодирует JWT, возвращает payload или None при ошибке."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
