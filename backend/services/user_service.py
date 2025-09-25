import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import User
from schemas.user import (
    AdminUserCreate,
    SelfUpdateRequest,
    UserCreate,
    UserUpdate,
)
from services.administrative_service import AdministrativeService
from services.email_service import email_service
from utils.auth import get_password_hash, verify_password
from utils.constants import (
    CANNOT_DELETE_OWN_ACCOUNT,
    DELETE_FAILED,
    EMAIL_ALREADY_REGISTERED,
    INVALID_EMAIL_OR_PASSWORD,
    PHONE_ALREADY_IN_USE,
    PHONE_ALREADY_REGISTERED,
    UPDATE_FAILED,
    USER_ACCOUNT_INACTIVE,
    USER_CREATION_FAILED,
    USER_NOT_FOUND,
    USER_REGISTRATION_FAILED,
)


class UserService:
    @staticmethod
    def _check_user_exists(db: Session, email: str, phone_number: str) -> None:
        """
        Check if user already exists by email
        or phone number and raise appropriate exception
        """
        existing_user = (
            db.query(User)
            .filter(
                (User.email == email) | (User.phone_number == phone_number)
            )
            .first()
        )

        if existing_user:
            if existing_user.email == email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=EMAIL_ALREADY_REGISTERED,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=PHONE_ALREADY_REGISTERED,
                )

    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        # Check if user already exists
        UserService._check_user_exists(
            db, user_data.email, user_data.phone_number
        )

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            phone_number=user_data.phone_number,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            user_type=user_data.user_type,
        )

        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=USER_REGISTRATION_FAILED,
            )

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_EMAIL_OR_PASSWORD,
            )
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_EMAIL_OR_PASSWORD,
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=USER_ACCOUNT_INACTIVE,
            )
        return user

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def generate_invitation_token() -> str:
        """Generate a secure invitation token"""
        return str(uuid.uuid4())

    @staticmethod
    async def admin_create_user(
        db: Session,
        user_data: AdminUserCreate,
        invited_by_name: str = "Administrator",
    ) -> tuple[User, bool]:
        """Create user by admin with email invitation"""
        # Check if user already exists
        UserService._check_user_exists(
            db, user_data.email, user_data.phone_number
        )

        # Generate invitation token and expiration
        invitation_token = UserService.generate_invitation_token()
        invitation_expires_at = datetime.utcnow() + timedelta(days=7)

        # Create new user with invitation
        db_user = User(
            email=user_data.email,
            phone_number=user_data.phone_number,
            hashed_password=None,  # No password until user accepts invitation
            full_name=user_data.full_name,
            user_type=user_data.user_type,
            is_active=False,  # Inactive until invitation accepted
            invitation_token=invitation_token,
            invitation_sent_at=datetime.utcnow(),
            invitation_expires_at=invitation_expires_at,
        )

        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)

            # Assign administrative areas if provided
            if user_data.administrative_ids:
                from schemas.administrative import AdministrativeAssign

                try:
                    assignment_data = AdministrativeAssign(
                        administrative_ids=user_data.administrative_ids
                    )
                    AdministrativeService.assign_user_to_administrative(
                        db, db_user.id, assignment_data
                    )
                except ValueError as e:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=str(e)
                    )

            # Send invitation email
            email_sent = await email_service.send_invitation_email(
                email=user_data.email,
                full_name=user_data.full_name,
                invitation_token=invitation_token,
                user_type=user_data.user_type.value,
                invited_by_name=invited_by_name,
            )

            return db_user, email_sent

        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=USER_CREATION_FAILED,
            )

    @staticmethod
    def get_users_list(
        db: Session, page: int = 1, size: int = 10, search: str = None
    ) -> tuple[list[User], int]:
        """Get paginated list of users with optional search"""
        query = db.query(User)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.full_name.ilike(search_term),
                    User.email.ilike(search_term),
                    User.phone_number.ilike(search_term),
                )
            )

        total = query.count()
        users = query.offset((page - 1) * size).limit(size).all()

        return users, total

    @staticmethod
    def verify_invitation_token(
        db: Session, invitation_token: str
    ) -> tuple[bool, bool, User]:
        """
        Verify invitation token validity and expiration

        Returns:
            tuple: (is_valid, is_expired, user_or_none)
        """
        user = (
            db.query(User)
            .filter(User.invitation_token == invitation_token)
            .first()
        )

        if not user:
            return False, False, None

        if user.is_active:
            return False, False, user  # Already activated

        # Handle timezone-aware comparison
        current_time = datetime.utcnow()
        if user.invitation_expires_at.tzinfo is not None:
            # If invitation_expires_at is timezone-aware, make current_time
            # timezone-aware
            from datetime import timezone

            current_time = current_time.replace(tzinfo=timezone.utc)

        is_expired = current_time > user.invitation_expires_at
        return True, is_expired, user

    @staticmethod
    def accept_invitation(
        db: Session, invitation_token: str, password: str
    ) -> User:
        """Accept invitation and activate user account"""
        is_valid, is_expired, user = UserService.verify_invitation_token(
            db, invitation_token
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid invitation token",
            )

        if is_expired:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation token has expired",
            )

        if user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is already activated",
            )

        try:
            # Set password and activate account
            user.hashed_password = get_password_hash(password)
            user.is_active = True
            user.password_set_at = datetime.utcnow()
            user.invitation_token = None  # Clear token after use

            db.commit()
            db.refresh(user)
            return user

        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to activate account",
            )

    @staticmethod
    async def resend_invitation(
        db: Session, user_id: int, invited_by_name: str = "Administrator"
    ) -> bool:
        """Resend invitation email to user"""
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND
            )

        if user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is already active",
            )

        try:
            # Generate new invitation token and expiration
            user.invitation_token = UserService.generate_invitation_token()
            user.invitation_sent_at = datetime.utcnow()
            user.invitation_expires_at = datetime.utcnow() + timedelta(days=7)

            db.commit()
            db.refresh(user)

            # Send invitation email
            email_sent = await email_service.send_invitation_email(
                email=user.email,
                full_name=user.full_name,
                invitation_token=user.invitation_token,
                user_type=user.user_type.value,
                invited_by_name=invited_by_name,
            )

            return email_sent

        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resend invitation",
            )

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Get user by ID"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND
            )
        return user

    @staticmethod
    def update_user(
        db: Session, user_id: int, user_data: UserUpdate, current_user: User
    ) -> User:
        """Update user details"""
        user = UserService.get_user_by_id(db, user_id)

        # Check for conflicts if updating email or phone
        if (
            user_data.phone_number
            and user_data.phone_number != user.phone_number
        ):
            existing_user = (
                db.query(User)
                .filter(
                    User.phone_number == user_data.phone_number,
                    User.id != user_id,
                )
                .first()
            )
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=PHONE_ALREADY_IN_USE,
                )

        # Prevent users from changing their own role
        if user_data.user_type is not None and user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change your own role",
            )

        # Update fields
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
        if user_data.phone_number is not None:
            user.phone_number = user_data.phone_number
        if user_data.user_type is not None:
            user.user_type = user_data.user_type

        try:
            db.commit()
            db.refresh(user)
            return user
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=UPDATE_FAILED,
            )

    @staticmethod
    def delete_user(db: Session, user_id: int, current_user: User) -> bool:
        """Delete user (admin only, cannot delete self)"""
        if current_user.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=CANNOT_DELETE_OWN_ACCOUNT,
            )

        user = UserService.get_user_by_id(db, user_id)

        try:
            db.delete(user)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=DELETE_FAILED,
            )

    @staticmethod
    def update_self(
        db: Session, current_user: User, update_data: SelfUpdateRequest
    ) -> User:
        """Update current user's own account (excludes role changes)"""
        # Validate password fields if provided
        if update_data.new_password or update_data.current_password:
            if not (update_data.new_password and update_data.current_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="current_password and new_password are required",
                )

            # Verify current password
            if not verify_password(
                update_data.current_password, current_user.hashed_password
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect",
                )

            # Check if new password is different
            if verify_password(
                update_data.new_password, current_user.hashed_password
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New password must be different",
                )

        # Check phone number conflicts if updating
        if (
            update_data.phone_number
            and update_data.phone_number != current_user.phone_number
        ):
            existing_user = (
                db.query(User)
                .filter(
                    User.phone_number == update_data.phone_number,
                    User.id != current_user.id,
                )
                .first()
            )
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=PHONE_ALREADY_IN_USE,
                )

        # Update fields
        if update_data.full_name is not None:
            current_user.full_name = update_data.full_name
        if update_data.phone_number is not None:
            current_user.phone_number = update_data.phone_number
        if update_data.new_password is not None:
            current_user.hashed_password = get_password_hash(
                update_data.new_password
            )

        try:
            db.commit()
            db.refresh(current_user)
            return current_user
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=UPDATE_FAILED,
            )
