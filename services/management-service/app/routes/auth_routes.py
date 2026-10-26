from fastapi import APIRouter, Depends

from app.controllers.auth_controller import auth_controller
from app.core.dependencies import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse, UserAuthInfo

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and receive a JWT access token",
)
def login(login_data: LoginRequest):
    return auth_controller.login(login_data)


@router.get(
    "/me",
    response_model=UserAuthInfo,
    summary="Get profile of currently authenticated user",
)
def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
):
    return auth_controller.get_me(current_user)
