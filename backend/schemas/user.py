from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from models.user import UserType
from utils.validators import validate_phone_number


class UserCreate(BaseModel):
    email: EmailStr
    phone_number: str
    password: str
    full_name: str
    user_type: UserType

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number_field(cls, v):
        return validate_phone_number(v)

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
    is_active: bool
    invitation_status: Optional[str] = None
    password_set_at: Optional[datetime] = None


class UserDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: str
    phone_number: str
    full_name: str
    user_type: UserType
    is_active: bool
    invitation_token: Optional[str] = None
    invitation_sent_at: Optional[datetime] = None
    invitation_expires_at: Optional[datetime] = None
    password_set_at: Optional[datetime] = None
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
    def validate_phone_number_field(cls, v):
        return validate_phone_number(v)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    user_type: Optional[UserType] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number_field(cls, v):
        if v:
            return validate_phone_number(v)
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SelfUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number_field(cls, v):
        if v:
            return validate_phone_number(v)
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if v and len(v) < 8:
            raise ValueError("New password must be at least 8 characters long")
        return v

    @classmethod
    def validate_password_fields(cls, values):
        current_password = values.get('current_password')
        new_password = values.get('new_password')
        
        # If changing password, both fields are required
        if new_password and not current_password:
            raise ValueError("current_password is required when changing password")
        if current_password and not new_password:
            raise ValueError("new_password is required when providing current_password")
        
        return values


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# New invitation-related schemas
class AcceptInvitationRequest(BaseModel):
    invitation_token: str
    password: str
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class InvitationStatusResponse(BaseModel):
    valid: bool
    expired: bool
    user_info: Optional[dict] = None
    error_message: Optional[str] = None


class AdminUserCreateResponse(BaseModel):
    message: str
    user: UserResponse
    invitation_sent: bool
    invitation_url: Optional[str] = None
