from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from schemas.user import (
    AdminUserCreate,
    UserDetailResponse,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from services.user_service import UserService
from utils.auth_dependencies import admin_required
from models.user import User

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("/", response_model=UserListResponse)
def get_users_list(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Get paginated list of users with optional search (Admin only)"""
    users, total = UserService.get_users_list(db, page, size, search)

    return UserListResponse(
        users=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        size=size,
    )


@router.post("/", response_model=dict)
def create_user_by_admin(
    user_data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Create a new user by admin with temporary password"""
    user, temp_password = UserService.admin_create_user(db, user_data)

    return {
        "message": "User created successfully",
        "user": UserResponse.model_validate(user),
        "temporary_password": temp_password,
    }


@router.get("/{user_id}", response_model=UserDetailResponse)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Get user details (Admin only)"""
    user = UserService.get_user_by_id(db, user_id)
    return UserDetailResponse.model_validate(user)


@router.put("/{user_id}/", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Update user details (Admin only)"""
    user = UserService.update_user(db, user_id, user_data, current_user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}/")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Delete user (Admin only, cannot delete self)"""
    UserService.delete_user(db, user_id, current_user)
    return {"message": "User deleted successfully"}
