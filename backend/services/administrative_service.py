from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import Administrative, AdministrativeLevel, UserAdministrative
from schemas.administrative import (
    AdministrativeAssign,
    AdministrativeCreate,
    AdministrativeUpdate,
)


class AdministrativeService:
    @staticmethod
    def get_all_administrative(db: Session) -> List[Administrative]:
        """Get all administrative areas"""
        return db.query(Administrative).order_by(Administrative.path).all()

    @staticmethod
    def get_administrative_by_id(
        db: Session, administrative_id: int
    ) -> Administrative:
        """Get administrative area by ID"""
        admin = (
            db.query(Administrative)
            .filter(Administrative.id == administrative_id)
            .first()
        )
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Administrative area not found",
            )
        return admin

    @staticmethod
    def get_administrative_by_level(
        db: Session, level: str
    ) -> List[Administrative]:
        """Get administrative areas by level"""
        return (
            db.query(Administrative)
            .join(AdministrativeLevel)
            .filter(AdministrativeLevel.name == level)
            .all()
        )

    @staticmethod
    def get_administrative_by_parent(
        db: Session, parent_id: int
    ) -> List[Administrative]:
        """Get administrative areas by parent ID"""
        return (
            db.query(Administrative)
            .filter(Administrative.parent_id == parent_id)
            .all()
        )

    @staticmethod
    def create_administrative(
        db: Session, administrative_data: AdministrativeCreate
    ) -> Administrative:
        """Create a new administrative area"""
        # Check if code already exists at this level
        level_obj = (
            db.query(AdministrativeLevel)
            .filter(AdministrativeLevel.name == administrative_data.level)
            .first()
        )

        if not level_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrative level '{}' not found".format(
                    administrative_data.level
                ),
            )

        # Check for duplicate code at this level
        existing = (
            db.query(Administrative)
            .filter(
                Administrative.code == administrative_data.code,
                Administrative.level_id == level_obj.id,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                # flake8: noqa=E501
                detail="Administrative area with code '{}' already exists at this level".format(
                    administrative_data.code
                ),
            )

        # Validate parent exists if provided
        if administrative_data.parent_id:
            parent = AdministrativeService.get_administrative_by_id(
                db, administrative_data.parent_id
            )

        # Build path
        path = administrative_data.code
        if administrative_data.parent_id:
            parent = AdministrativeService.get_administrative_by_id(
                db, administrative_data.parent_id
            )
            path = f"{parent.path}.{administrative_data.code}"

        admin = Administrative(
            code=administrative_data.code,
            name=administrative_data.name,
            level_id=level_obj.id,
            parent_id=administrative_data.parent_id,
            path=path,
        )

        try:
            db.add(admin)
            db.commit()
            db.refresh(admin)
            return admin
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create administrative area",
            )

    @staticmethod
    def update_administrative(
        db: Session, administrative_id: int, update_data: AdministrativeUpdate
    ) -> Administrative:
        """Update administrative area"""
        admin = AdministrativeService.get_administrative_by_id(
            db, administrative_id
        )

        # Update fields
        if update_data.name is not None:
            admin.name = update_data.name

        if update_data.parent_id is not None:
            # Validate parent exists and is not self
            if update_data.parent_id == administrative_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Administrative area cannot be its own parent",
                )

            if update_data.parent_id:
                parent = AdministrativeService.get_administrative_by_id(
                    db, update_data.parent_id
                )
            admin.parent_id = update_data.parent_id

        try:
            db.commit()
            db.refresh(admin)
            return admin
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update administrative area",
            )

    @staticmethod
    def assign_user_to_administrative(
        db: Session, user_id: int, assignment_data: AdministrativeAssign
    ) -> List[UserAdministrative]:
        """Assign user to administrative areas"""
        # Clear existing assignments
        db.query(UserAdministrative).filter(
            UserAdministrative.user_id == user_id
        ).delete()

        # Create new assignments
        assignments = []
        for admin_id in assignment_data.administrative_ids:
            # Verify administrative area exists
            AdministrativeService.get_administrative_by_id(db, admin_id)

            assignment = UserAdministrative(
                user_id=user_id,
                administrative_id=admin_id,
            )
            db.add(assignment)
            assignments.append(assignment)

        try:
            db.commit()
            return assignments
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to assign user to administrative areas",
            )

    @staticmethod
    def get_user_administrative(
        db: Session, user_id: int
    ) -> List[Administrative]:
        """Get administrative areas assigned to a user"""
        return (
            db.query(Administrative)
            .join(UserAdministrative)
            .filter(UserAdministrative.user_id == user_id)
            .all()
        )
