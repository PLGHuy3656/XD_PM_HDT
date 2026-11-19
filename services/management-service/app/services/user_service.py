from typing import List, Optional
from app.core.security import hash_password
from app.repositories.user_repository import UserRepository, user_repository
from app.schemas.user import UserCreateRequest, UserResponse, UserUpdateRequest


class UserService:
    def __init__(self, repository: UserRepository = user_repository):
        self.repository = repository

    def list_users(self, limit: int = 100, offset: int = 0) -> List[UserResponse]:
        raw_users = self.repository.list_users(limit=limit, offset=offset)
        return [UserResponse(**u) for u in raw_users]

    def get_user(self, user_id: str) -> Optional[UserResponse]:
        user = self.repository.get_user_by_id(user_id)
        if not user:
            return None
        return UserResponse(**user)

    def create_user(self, req: UserCreateRequest) -> UserResponse:
        existing = self.repository.get_user_by_email(req.email)
        if existing:
            raise ValueError(f"User with email '{req.email}' already exists")

        pwd_hash = hash_password(req.password)
        created = self.repository.create_user(
            email=req.email,
            password_hash=pwd_hash,
            full_name=req.full_name,
            phone=req.phone,
            role=req.role,
            status=req.status,
        )
        return UserResponse(**created)

    def update_user(self, user_id: str, req: UserUpdateRequest) -> Optional[UserResponse]:
        existing = self.repository.get_user_by_id(user_id)
        if not existing:
            return None

        updated = self.repository.update_user(
            user_id=user_id,
            full_name=req.full_name,
            phone=req.phone,
            status=req.status,
            role=req.role,
        )
        return UserResponse(**updated) if updated else None

    def update_user_status(self, user_id: str, status: str) -> bool:
        existing = self.repository.get_user_by_id(user_id)
        if not existing:
            return False
        return self.repository.update_user_status(user_id, status)

    def delete_user(self, user_id: str) -> bool:
        return self.repository.delete_user(user_id)


user_service = UserService()
