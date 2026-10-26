from fastapi import HTTPException, status

from app.schemas.auth import LoginRequest, TokenResponse, UserAuthInfo
from app.services.auth_service import AuthService, auth_service


class AuthController:
    def __init__(self, service: AuthService = auth_service):
        self.service = service

    def login(self, login_data: LoginRequest) -> TokenResponse:
        """Handles user login and issues JWT."""
        try:
            result = self.service.authenticate(
                email=login_data.email,
                password=login_data.password,
            )
            return TokenResponse(**result)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def get_me(self, current_user: dict) -> UserAuthInfo:
        """Returns the authenticated user's profile and roles."""
        return UserAuthInfo(
            id=str(current_user["id"]),
            email=current_user["email"],
            full_name=current_user["full_name"],
            roles=current_user.get("roles") or [],
        )


auth_controller = AuthController()
