import os
from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_db
from models.user import User, UserType
from models.administrative import Administrative
from schemas.user import (
    AcceptInvitationRequest,
    InvitationStatusResponse,
    LoginRequest,
    SelfUpdateRequest,
    TokenResponse,
    UserResponse,
)
from services.user_service import UserService
from utils.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from utils.auth_dependencies import get_current_user

# Configuration for cookie security
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login_user(
    login_data: LoginRequest, response: Response, db: Session = Depends(get_db)
):
    """Login user and return access token with httpOnly refresh token cookie"""
    user = UserService.authenticate_user(
        db, login_data.email, login_data.password
    )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_type": user.user_type.value},
        expires_delta=access_token_expires,
    )

    # Create refresh token
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        data={"sub": user.email, "user_type": user.user_type.value},
        expires_delta=refresh_token_expires,
    )

    # Set httpOnly cookie for refresh token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # 7 days in seconds
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        path="/",
    )

    # Get user administrative info
    admin_info = UserService._get_user_administrative_info(db, user.id)
    # Build user response with administrative location
    user_response = UserResponse.model_validate(user)
    # If no administrative info and user is admin, assign national level
    if not admin_info.get('id') and user.user_type == UserType.ADMIN:
        national_adm = (
            db.query(Administrative)
            .filter(Administrative.parent_id.is_(None))
            .first()
        )
        if national_adm:
            admin_info = {
                'id': national_adm.id,
                'full_path': national_adm.name
            }
    user_response.administrative_location = admin_info

    return TokenResponse(
        access_token=access_token, user=user_response
    )


@router.post("/refresh", response_model=dict)
def refresh_token(
    refresh_token: str = Cookie(None), db: Session = Depends(get_db)
):
    """Refresh access token using the httpOnly refresh token cookie"""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )

    # Verify refresh token
    payload = verify_refresh_token(refresh_token)
    email = payload.get("sub")
    user_type = payload.get("user_type")

    # Get user from database to ensure they still exist and are active
    user = UserService.get_user_by_email(db, email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": email, "user_type": user_type},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
def logout_user(response: Response):
    """Logout user by clearing the refresh token cookie"""
    response.delete_cookie(
        key="refresh_token",
        path="/",
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
    )
    return {"message": "Logged out successfully"}


@router.get("/profile", response_model=UserResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile"""
    # Get user administrative info
    admin_info = UserService._get_user_administrative_info(db, current_user.id)
    # Build user response with administrative location
    user_response = UserResponse.model_validate(current_user)
    user_response.administrative_location = admin_info
    return user_response


@router.put("/profile", response_model=UserResponse)
def update_profile(
    update_data: SelfUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user's profile and optionally change password"""
    updated_user = UserService.update_self(db, current_user, update_data)
    # Get user administrative info
    admin_info = UserService._get_user_administrative_info(db, updated_user.id)
    # Build user response with administrative location
    user_response = UserResponse.model_validate(updated_user)
    user_response.administrative_location = admin_info
    return user_response


@router.get(
    "/verify-invitation/{invitation_token}",
    response_model=InvitationStatusResponse,
)
def verify_invitation(invitation_token: str, db: Session = Depends(get_db)):
    """Verify invitation token validity and get user info"""
    is_valid, is_expired, user = UserService.verify_invitation_token(
        db, invitation_token
    )

    if not is_valid:
        return InvitationStatusResponse(
            valid=False,
            expired=False,
            error_message="Invalid invitation token",
        )

    if is_expired:
        return InvitationStatusResponse(
            valid=False,
            expired=True,
            error_message="Invitation token has expired",
        )

    if user.is_active:
        return InvitationStatusResponse(
            valid=False,
            expired=False,
            error_message="Account is already activated",
        )

    return InvitationStatusResponse(
        valid=True,
        expired=False,
        user_info={
            "email": user.email,
            "full_name": user.full_name,
            "user_type": user.user_type.value,
        },
    )


@router.post("/accept-invitation", response_model=TokenResponse)
def accept_invitation(
    request: AcceptInvitationRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Accept invitation and set password, then login user"""
    # Accept invitation and activate account
    user = UserService.accept_invitation(
        db, request.invitation_token, request.password
    )

    # Create access token for the newly activated user
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_type": user.user_type.value},
        expires_delta=access_token_expires,
    )

    # Create refresh token
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        data={"sub": user.email, "user_type": user.user_type.value},
        expires_delta=refresh_token_expires,
    )

    # Set httpOnly cookie for refresh token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # 7 days in seconds
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        path="/",
    )

    # Get user administrative info
    admin_info = UserService._get_user_administrative_info(db, user.id)
    # Build user response with administrative location
    user_response = UserResponse.model_validate(user)
    user_response.administrative_location = admin_info

    return TokenResponse(
        access_token=access_token, user=user_response
    )
