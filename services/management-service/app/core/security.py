from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.config import settings

# Initialize Argon2 password hasher
password_hasher = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2."""
    if not password:
        raise ValueError("Password cannot be empty")
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """
    Verifies a plaintext password against an Argon2 hash.
    Safely returns False if the hash is None or empty.
    """
    if not hashed_password or not plain_password:
        return False
    try:
        return password_hasher.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    subject: str,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Generates a signed JWT access token.
    Claims: sub (user_id), roles, iat, exp.
    """
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured in environment/.env")

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": str(subject),
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.
    Raises jwt.PyJWTError on invalid or expired token.
    """
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured in environment/.env")

    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
