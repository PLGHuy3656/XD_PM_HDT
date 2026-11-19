from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class RoleEnum(str, Enum):
    ADMIN = "ADMIN"
    FARM_OWNER = "FARM_OWNER"
    TECHNICIAN = "TECHNICIAN"


class UserStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    INACTIVE = "INACTIVE"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    status: str
    roles: List[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    phone: Optional[str] = None
    role: str = "FARM_OWNER"
    status: str = "ACTIVE"


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class UserStatusUpdateRequest(BaseModel):
    status: str
