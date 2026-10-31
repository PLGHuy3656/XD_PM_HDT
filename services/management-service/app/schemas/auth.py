from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class UserAuthInfo(BaseModel):
    id: str
    email: str
    full_name: str
    roles: list[str] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserAuthInfo


class TokenPayload(BaseModel):
    sub: str
    roles: list[str] = []
    exp: int | None = None
