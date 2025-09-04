from datetime import timedelta
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from schemas.user import UserCreate, UserResponse, LoginRequest, TokenResponse
from services.user_service import UserService
from utils.auth import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    user = UserService.create_user(db, user_data)
    return UserResponse.model_validate(user)


@router.post("/login/", response_model=TokenResponse)
def login_user(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Login user and return access token"""
    user = UserService.authenticate_user(
        db, login_data.email, login_data.password
    )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_type": user.user_type.value},
        expires_delta=access_token_expires,
    )

    return TokenResponse(
        access_token=access_token, user=UserResponse.model_validate(user)
    )
