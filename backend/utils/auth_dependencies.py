from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models.user import User, UserType
from services.user_service import UserService
from utils.auth import verify_token
from utils.constants import (
    ADMIN_ACCESS_REQUIRED,
    INACTIVE_USER,
    INVALID_AUTH_CREDENTIALS,
    USER_NOT_FOUND,
    WWW_AUTHENTICATE_HEADER,
)

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_AUTH_CREDENTIALS,
                headers={"WWW-Authenticate": WWW_AUTHENTICATE_HEADER},
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_AUTH_CREDENTIALS,
            headers={"WWW-Authenticate": WWW_AUTHENTICATE_HEADER},
        )

    user = UserService.get_user_by_email(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=USER_NOT_FOUND,
            headers={"WWW-Authenticate": WWW_AUTHENTICATE_HEADER},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INACTIVE_USER,
            headers={"WWW-Authenticate": WWW_AUTHENTICATE_HEADER},
        )

    return user


def admin_required(current_user: User = Depends(get_current_user)) -> User:
    """Require admin user type"""
    if current_user.user_type != UserType.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ADMIN_ACCESS_REQUIRED,
        )
    return current_user
