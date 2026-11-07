"""Вход в веб-интерфейс: один пользователь admin, пароль задаёт человек при первом запуске.

Пароль хранится только в виде хеша scrypt (стандартная библиотека Python).
Сессия - подписанный токен в HttpOnly-cookie; ключ подписи лежит в базе,
поэтому смена/сброс пароля сразу завершает все открытые сессии.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from sqlalchemy.future import select

import models

COOKIE_NAME = "pbx_session"
SESSION_TTL = 24 * 3600          # сутки
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128

_N, _R, _P = 2 ** 14, 8, 1


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def validate_password(password: str):
    """Возвращает текст ошибки или None, если пароль подходит."""
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters"
    if len(password) > MAX_PASSWORD_LEN:
        return f"Password must be at most {MAX_PASSWORD_LEN} characters"
    return None


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=_unb64(salt),
                              n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, _unb64(digest))
    except Exception:
        return False


def make_token(secret: str, ttl: int = SESSION_TTL, now: float = None) -> str:
    exp = int((now if now is not None else time.time()) + ttl)
    payload = _b64(json.dumps({"exp": exp}).encode())
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{_b64(sig)}"


def verify_token(secret: str, token: str, now: float = None) -> bool:
    try:
        payload, sig = token.split(".")
        good = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(good, _unb64(sig)):
            return False
        exp = json.loads(_unb64(payload))["exp"]
        return (now if now is not None else time.time()) < exp
    except Exception:
        return False


# ---- работа с базой ----------------------------------------------------------

async def get_admin(db):
    result = await db.execute(select(models.AdminAuth).where(models.AdminAuth.id == 1))
    return result.scalars().first()


async def set_password(db, password: str):
    """Создаёт или обновляет пароль admin и меняет ключ подписи сессий."""
    password_hash = await asyncio.to_thread(hash_password, password)
    admin = await get_admin(db)
    if admin is None:
        admin = models.AdminAuth(id=1, password_hash=password_hash,
                                 session_secret=secrets.token_hex(32))
        db.add(admin)
    else:
        admin.password_hash = password_hash
        admin.session_secret = secrets.token_hex(32)
    await db.commit()
    return admin


async def check_password(password: str, admin) -> bool:
    return await asyncio.to_thread(verify_password, password, admin.password_hash)
