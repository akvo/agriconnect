from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from models.user import UserType


class UserCreate(BaseModel):
    email: EmailStr
    phone_number: str
    password: str
    full_name: str
    user_type: UserType

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v):
        # Basic phone number validation
        if not v.startswith("+") or len(v) < 10:
            raise ValueError(
                "Phone number must start with + and be at least 10 characters"
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    phone_number: str
    full_name: str
    user_type: UserType
    is_active: str


class UserDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    phone_number: str
    full_name: str
    user_type: UserType
    is_active: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    size: int


class AdminUserCreate(BaseModel):
    email: EmailStr
    phone_number: str
    full_name: str
    user_type: UserType

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v):
        # Basic phone number validation
        if not v.startswith("+") or len(v) < 10:
            raise ValueError(
                "Phone number must start with + and be at least 10 characters"
            )
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    user_type: Optional[UserType] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v):
        if v and (not v.startswith("+") or len(v) < 10):
            raise ValueError(
                "Phone number must start with + and be at least 10 characters"
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
