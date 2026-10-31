from app.config import settings
from app.core.security import create_access_token, verify_password
from app.repositories.user_repository import UserRepository, user_repository


class AuthService:
    def __init__(self, repository: UserRepository = user_repository):
        self.repository = repository

    def authenticate(self, email: str, password: str) -> dict:
        """
        Authenticates a user via email and Argon2 password.
        Returns a signed JWT access token and sanitized user profile.
        Does not leak existence of user on failure.
        """
        if not email or not password:
            raise ValueError("Invalid email or password")

        clean_email = email.strip().lower()
        user = self.repository.get_user_by_email(clean_email)

        # Secure generic rejection: unknown user, inactive user, or uninitialized password_hash
        if not user or user.get("status") != "ACTIVE" or not user.get("password_hash"):
            raise ValueError("Invalid email or password")

        if not verify_password(password, user["password_hash"]):
            raise ValueError("Invalid email or password")

        roles = user.get("roles") or []
        user_id = str(user["id"])

        token = create_access_token(
            subject=user_id,
            roles=roles,
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "user": {
                "id": user_id,
                "email": user["email"],
                "full_name": user["full_name"],
                "roles": roles,
            },
        }

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Resolves authenticated user without exposing password_hash."""
        user = self.repository.get_user_by_id(user_id)
        if not user or user.get("status") != "ACTIVE":
            return None

        return {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "phone": user.get("phone"),
            "status": user["status"],
            "roles": user.get("roles") or [],
        }


auth_service = AuthService()
