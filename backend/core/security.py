from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/users/token", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire, "type": "refresh"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[int]:
    """Декодирует ACCESS-токен. Refresh-токен (type=refresh) сюда НЕ пройдёт —
    его нельзя использовать как access (иначе долгоживущий refresh = вечный доступ)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") == "refresh":
            return None
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


def create_reset_token(user_id: int, password_hash: str) -> str:
    """Одноразовый токен сброса пароля, живёт 60 минут.

    В токен зашивается отпечаток текущего хэша пароля (первые 16 символов).
    Как только пароль сменён, отпечаток перестаёт совпадать — ссылка из письма
    становится недействительной. Это и даёт одноразовость без отдельной таблицы:
    повторно тем же письмом пароль не поменять.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "reset", "fp": password_hash[:16]},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_reset_token(token: str) -> Optional[tuple[int, str]]:
    """Декодирует токен сброса. Возвращает (user_id, отпечаток) или None.

    Access/refresh-токены сюда не проходят — только type=reset.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "reset":
            return None
        return int(payload["sub"]), str(payload.get("fp", ""))
    except (JWTError, KeyError, ValueError):
        return None


def decode_refresh_token(token: str) -> Optional[int]:
    """Декодирует ТОЛЬКО refresh-токен (type=refresh). Access-токен сюда не пройдёт —
    защита от обмена украденного access на новую пару через /refresh."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
