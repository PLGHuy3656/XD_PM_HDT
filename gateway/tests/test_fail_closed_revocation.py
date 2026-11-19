"""
SWIFTLETCARE — Unit Tests for Gateway Fail-Closed Token Revocation (FR-UAM-02).
Verifies that:
1. Valid unrevoked tokens decode successfully.
2. Revoked tokens return HTTP 401 Unauthorized.
3. Expired tokens return HTTP 401 Unauthorized.
4. Redis connection errors strictly fail closed with HTTP 503 Service Unavailable.
5. Redis timeouts strictly fail closed with HTTP 503 Service Unavailable.
6. Unconfigured Redis client strictly fails closed with HTTP 503 Service Unavailable.
"""

import time
import jwt
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.auth import (
    decode_and_verify_token,
    is_token_revoked,
    TokenRevocationBackendError,
)
from app.config import settings


@pytest.fixture
def jwt_tokens():
    secret = settings.jwt_secret
    alg = settings.jwt_algorithm
    now = int(time.time())
    
    valid_payload = {
        "sub": "user-test-001",
        "email": "test@swiftletcare.dev",
        "roles": ["TECHNICIAN"],
        "iat": now,
        "exp": now + 3600,
    }
    valid_token = jwt.encode(valid_payload, secret, algorithm=alg)
    
    expired_payload = {
        "sub": "user-test-002",
        "roles": ["FARM_OWNER"],
        "iat": now - 7200,
        "exp": now - 3600,
    }
    expired_token = jwt.encode(expired_payload, secret, algorithm=alg)
    
    return {"valid": valid_token, "expired": expired_token}


def test_valid_token_healthy_redis(jwt_tokens):
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    with patch("app.auth.get_redis_client", return_value=mock_redis):
        payload = decode_and_verify_token(jwt_tokens["valid"])
        assert payload["sub"] == "user-test-001"
        assert payload["roles"] == ["TECHNICIAN"]


def test_revoked_token_healthy_redis(jwt_tokens):
    mock_redis = MagicMock()
    mock_redis.get.return_value = "1"
    with patch("app.auth.get_redis_client", return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            decode_and_verify_token(jwt_tokens["valid"])
        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail.lower()


def test_expired_token(jwt_tokens):
    with pytest.raises(HTTPException) as exc_info:
        decode_and_verify_token(jwt_tokens["expired"])
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_redis_connection_error_fail_closed(jwt_tokens):
    mock_redis = MagicMock()
    mock_redis.get.side_effect = ConnectionError("Connection refused by Redis")
    with patch("app.auth.get_redis_client", return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            decode_and_verify_token(jwt_tokens["valid"])
        assert exc_info.value.status_code == 503
        assert "unreachable" in exc_info.value.detail.lower() or "unavailable" in exc_info.value.detail.lower()


def test_redis_timeout_error_fail_closed(jwt_tokens):
    mock_redis = MagicMock()
    mock_redis.get.side_effect = TimeoutError("Redis socket timeout")
    with patch("app.auth.get_redis_client", return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            decode_and_verify_token(jwt_tokens["valid"])
        assert exc_info.value.status_code == 503
        assert "unreachable" in exc_info.value.detail.lower() or "unavailable" in exc_info.value.detail.lower()


def test_redis_unconfigured_fail_closed(jwt_tokens):
    with patch("app.auth.get_redis_client", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            decode_and_verify_token(jwt_tokens["valid"])
        assert exc_info.value.status_code == 503
