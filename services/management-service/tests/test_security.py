from datetime import timedelta
import time
import jwt
import pytest

from app.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.fixture(autouse=True)
def setup_jwt_secret():
    old_secret = settings.jwt_secret
    if not settings.jwt_secret:
        settings.jwt_secret = "test_jwt_secret_key_for_unit_tests_32_bytes_long"
    yield
    settings.jwt_secret = old_secret


def test_password_hashing_uses_argon2():
    password = "SafeTestPassword123"
    hashed = hash_password(password)

    # Must not be plaintext
    assert hashed != password
    # Must use Argon2 format
    assert hashed.startswith("$argon2id$")


def test_password_verification():
    password = "CorrectPassword456"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, "") is False
    assert verify_password(password, None) is False


def test_create_and_decode_access_token():
    user_id = "11111111-1111-1111-1111-111111111111"
    roles = ["TECHNICIAN"]

    token = create_access_token(subject=user_id, roles=roles)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["roles"] == roles
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_reject_expired_token():
    user_id = "test-user-uuid"
    token = create_access_token(
        subject=user_id,
        roles=["ADMIN"],
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_reject_invalid_signature():
    user_id = "test-user-uuid"
    token = create_access_token(subject=user_id, roles=["ADMIN"])

    # Attempt to decode with a different secret
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "completely_wrong_secret_key_32_bytes_long", algorithms=["HS256"])


def test_reject_malformed_token():
    with pytest.raises(jwt.DecodeError):
        decode_access_token("this.is.not.a.valid.jwt")
