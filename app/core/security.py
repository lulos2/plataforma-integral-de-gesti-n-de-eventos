from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# Avoid bcrypt backend issues/version mismatches in containers.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGORITHM = "HS256"


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _get_secret_key() -> str:
    # Dev default is set in Settings; override with SECRET_KEY.
    return get_settings().secret_key


def create_access_token(
    *, subject: str, session_version: int = 0, expires_minutes: int | None = None
) -> str:
    if expires_minutes is None:
        expires_minutes = get_settings().access_token_expire_minutes

    now = datetime.now(UTC)
    expire = now + timedelta(minutes=expires_minutes)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": expire,
        "session_version": session_version,
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token, _get_secret_key(), algorithms=[ALGORITHM], options={"require_exp": True}
        )
    except JWTError:
        return None
    version = payload.get("session_version")
    if not isinstance(payload.get("sub"), str) or type(version) is not int or version < 0:
        return None
    return payload


def generate_reset_token() -> str:
    # Alta entropia: no hace falta un hash lento (bcrypt/pbkdf2) como con
    # passwords elegidas por personas, ya que esto no es adivinable.
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
