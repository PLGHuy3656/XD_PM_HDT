import pytest

from app.config import settings
from app.core.security import hash_password
from app.services.auth_service import AuthService


class FakeUserRepository:
    def __init__(self):
        self.users = {
            "tech@nestmate.dev": {
                "id": "11111111-1111-1111-1111-111111111111",
                "email": "tech@nestmate.dev",
                "password_hash": hash_password("ValidPassword123"),
                "full_name": "Nguyen Van Technician",
                "phone": "0900000001",
                "status": "ACTIVE",
                "roles": ["TECHNICIAN"],
            },
            "unprovisioned@nestmate.dev": {
                "id": "22222222-2222-2222-2222-222222222222",
                "email": "unprovisioned@nestmate.dev",
                "password_hash": None,
                "full_name": "Unprovisioned User",
                "phone": None,
                "status": "ACTIVE",
                "roles": ["FARM_OWNER"],
            },
            "inactive@nestmate.dev": {
                "id": "33333333-3333-3333-3333-333333333333",
                "email": "inactive@nestmate.dev",
                "password_hash": hash_password("InactivePassword"),
                "full_name": "Inactive User",
                "phone": None,
                "status": "INACTIVE",
                "roles": ["TECHNICIAN"],
            },
        }

    def get_user_by_email(self, email: str):
        return self.users.get(email.lower())

    def get_user_by_id(self, user_id: str):
        for u in self.users.values():
            if u["id"] == user_id:
                return u
        return None


@pytest.fixture(autouse=True)
def setup_jwt_secret():
    old_secret = settings.jwt_secret
    if not settings.jwt_secret:
        settings.jwt_secret = "test_jwt_secret_key_for_unit_tests_32_bytes_long"
    yield
    settings.jwt_secret = old_secret


@pytest.fixture
def auth_service():
    return AuthService(repository=FakeUserRepository())


def test_authenticate_valid_credentials(auth_service):
    result = auth_service.authenticate("tech@nestmate.dev", "ValidPassword123")

    assert "access_token" in result
    assert result["token_type"] == "bearer"
    assert result["expires_in"] > 0
    assert result["user"]["email"] == "tech@nestmate.dev"
    assert result["user"]["roles"] == ["TECHNICIAN"]

    # SECURITY: password_hash must never be returned
    assert "password_hash" not in result
    assert "password_hash" not in result["user"]


def test_authenticate_invalid_password(auth_service):
    with pytest.raises(ValueError, match="Invalid email or password"):
        auth_service.authenticate("tech@nestmate.dev", "WrongPassword")


def test_authenticate_unknown_user(auth_service):
    with pytest.raises(ValueError, match="Invalid email or password"):
        auth_service.authenticate("nonexistent@nestmate.dev", "AnyPassword")


def test_authenticate_null_password_hash_safely_denied(auth_service):
    # Existing user with password_hash=None must be safely rejected
    with pytest.raises(ValueError, match="Invalid email or password"):
        auth_service.authenticate("unprovisioned@nestmate.dev", "SomePassword")


def test_authenticate_inactive_user_denied(auth_service):
    with pytest.raises(ValueError, match="Invalid email or password"):
        auth_service.authenticate("inactive@nestmate.dev", "InactivePassword")


def test_authenticate_empty_credentials(auth_service):
    with pytest.raises(ValueError, match="Invalid email or password"):
        auth_service.authenticate("", "Password")
    with pytest.raises(ValueError, match="Invalid email or password"):
        auth_service.authenticate("tech@nestmate.dev", "")


def test_get_user_by_id_excludes_password_hash(auth_service):
    user = auth_service.get_user_by_id("11111111-1111-1111-1111-111111111111")
    assert user is not None
    assert user["email"] == "tech@nestmate.dev"
    assert "password_hash" not in user
