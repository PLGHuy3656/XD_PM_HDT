"""Pytest fixtures for API Gateway testing (CP11.3)."""
import os

# Set explicit test secret before loading app configuration
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-gateway-dev-only-32chars")

from datetime import datetime, timedelta, timezone
from typing import List, Optional
import jwt
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.main import app, create_gateway_app


def make_jwt_token(
    user_id: str = "00000000-0000-0000-0000-000000000001",
    roles: Optional[List[str]] = None,
    email: str = "test@swiftletcare.vn",
    expires_in_minutes: int = 60,
    secret: Optional[str] = None,
    algorithm: str = "HS256",
) -> str:
    """Generates a valid signed JWT for testing."""
    if roles is None:
        roles = ["ADMIN"]
    key = secret if secret is not None else settings.jwt_secret
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_in_minutes)
    payload = {
        "sub": user_id,
        "roles": roles,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, key, algorithm=algorithm)


@pytest.fixture
def make_token():
    return make_jwt_token


@pytest.fixture
def admin_token():
    return make_jwt_token(roles=["ADMIN"], email="admin@swiftletcare.vn")


@pytest.fixture
def tech_token():
    return make_jwt_token(
        user_id="11111111-1111-1111-1111-111111111111",
        roles=["TECHNICIAN"],
        email="tech@swiftletcare.vn",
    )


@pytest.fixture
def owner_token():
    return make_jwt_token(
        user_id="22222222-2222-2222-2222-222222222222",
        roles=["FARM_OWNER"],
        email="owner@swiftletcare.vn",
    )


@pytest.fixture
def client():
    """Standard synchronous test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fresh_app():
    """Returns a freshly created FastAPI app instance."""
    return create_gateway_app()
