import datetime
import hashlib
import uuid
from typing import Optional

import bcrypt
import jwt

from configs import config
from utils.date import now_local


def _secret_key() -> str:
    return config.AUTH_SECRET_KEY


def _access_token_expire_minutes() -> int:
    return config.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES


def _refresh_token_expire_minutes() -> int:
    return config.AUTH_REFRESH_TOKEN_EXPIRE_MINUTES


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_token(token: str) -> str:
    """Hash a token so the raw refresh token is never stored in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, username: str, role: str) -> str:
    """Create a JWT access token."""
    now = now_local()
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + datetime.timedelta(minutes=_access_token_expire_minutes()),
    }
    return jwt.encode(payload, _secret_key(), algorithm=config.AUTH_ALGORITHM)


def create_refresh_token(user_id: int, token_jti: str | None = None) -> str:
    """Create a JWT refresh token."""
    now = now_local()
    payload = {
        "sub": str(user_id),
        "jti": token_jti or str(uuid.uuid4()),
        "type": "refresh",
        "iat": now,
        "exp": now + datetime.timedelta(minutes=_refresh_token_expire_minutes()),
    }
    return jwt.encode(payload, _secret_key(), algorithm=config.AUTH_ALGORITHM)


def refresh_token_expiry(now: datetime.datetime | None = None) -> datetime.datetime:
    """Return the refresh-token expiry timestamp for a newly issued token."""
    base = now or now_local()
    return base + datetime.timedelta(minutes=_refresh_token_expire_minutes())


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns None if invalid."""
    try:
        return jwt.decode(token, _secret_key(), algorithms=[config.AUTH_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def extract_token_jti(token: str) -> str | None:
    """Return the token jti when the token is valid."""
    payload = decode_token(token)
    if not payload:
        return None
    jti = payload.get("jti")
    return str(jti) if jti else None
