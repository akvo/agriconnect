"""
Device registration router for push notifications.

Implements device registration and management endpoints
for Expo push notifications.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import get_db
from models.device import Device
from models.user import User, UserType
from models.administrative import UserAdministrative
from schemas.device import (
    DeviceRegisterRequest,
    DeviceResponse,
    DeviceUpdateRequest,
)
from utils.auth_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post(
    "",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_device(
    device_data: DeviceRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Register a device for push notifications.

    - Devices are associated with both users and administrative areas
    - If push_token already exists, update it (upsert behavior)
    - Tracks which user is currently logged in on the device
    """
    try:
        # Verify user has access to this administrative area
        user_admin = (
            db.query(UserAdministrative)
            .filter(
                UserAdministrative.user_id == current_user.id,
                UserAdministrative.administrative_id ==
                device_data.administrative_id,
            )
            .first()
        )

        if not user_admin and current_user.user_type != UserType.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this administrative area",
            )

        # Check if this push token already exists
        existing_device = (
            db.query(Device)
            .filter(Device.push_token == device_data.push_token)
            .first()
        )

        if existing_device:
            # Update existing device with current user
            existing_device.user_id = current_user.id
            existing_device.administrative_id = device_data.administrative_id
            existing_device.app_version = device_data.app_version
            existing_device.is_active = True
            db.commit()
            db.refresh(existing_device)

            logger.info(
                f"Updated device {existing_device.id} "
                f"for user_id {current_user.id}, "
                f"administrative_id {device_data.administrative_id}"
            )

            return DeviceResponse(
                id=existing_device.id,
                user_id=existing_device.user_id,
                administrative_id=existing_device.administrative_id,
                push_token=existing_device.push_token,
                app_version=existing_device.app_version,
                is_active=existing_device.is_active,
                created_at=existing_device.created_at,
                updated_at=existing_device.updated_at,
            )

        # Create new device registration
        new_device = Device(
            user_id=current_user.id,
            administrative_id=device_data.administrative_id,
            push_token=device_data.push_token,
            app_version=device_data.app_version,
            is_active=True,
        )

        db.add(new_device)
        db.commit()
        db.refresh(new_device)

        logger.info(
            f"Registered new device {new_device.id} "
            f"for user_id {current_user.id}, "
            f"administrative_id {device_data.administrative_id}"
        )

        return DeviceResponse(
            id=new_device.id,
            user_id=new_device.user_id,
            administrative_id=new_device.administrative_id,
            push_token=new_device.push_token,
            app_version=new_device.app_version,
            is_active=new_device.is_active,
            created_at=new_device.created_at,
            updated_at=new_device.updated_at,
        )

    except HTTPException:
        # Re-raise HTTPExceptions without catching them
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device registration failed due to database constraint",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error registering device: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register device",
        )


@router.get("", response_model=List[DeviceResponse])
def list_user_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all devices in administrative areas assigned to current user.

    Returns devices from all wards where the user has access,
    including descendant wards for upper-level EOs.
    """
    from services.administrative_service import AdministrativeService

    # Get all administrative IDs for current user
    user_admin_ids = (
        db.query(UserAdministrative.administrative_id)
        .filter(UserAdministrative.user_id == current_user.id)
        .all()
    )

    # Collect all accessible ward IDs (including descendants)
    all_admin_ids = set()
    for ua in user_admin_ids:
        all_admin_ids.add(ua.administrative_id)
        descendant_ids = AdministrativeService.get_descendant_ward_ids(
            db, ua.administrative_id
        )
        all_admin_ids.update(descendant_ids)

    if not all_admin_ids:
        return []

    devices = (
        db.query(Device)
        .filter(Device.administrative_id.in_(list(all_admin_ids)))
        .order_by(Device.created_at.desc())
        .all()
    )

    return [
        DeviceResponse(
            id=device.id,
            user_id=device.user_id,
            administrative_id=device.administrative_id,
            push_token=device.push_token,
            app_version=device.app_version,
            is_active=device.is_active,
            created_at=device.created_at,
            updated_at=device.updated_at,
        )
        for device in devices
    ]


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    device_update: DeviceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a device (typically to disable push notifications).

    Users can only update devices in their assigned administrative areas.
    """
    device = db.query(Device).filter(Device.id == device_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check if user has access to this administrative area
    user_admin = (
        db.query(UserAdministrative)
        .filter(
            UserAdministrative.user_id == current_user.id,
            UserAdministrative.administrative_id == device.administrative_id,
        )
        .first()
    )

    if not user_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update devices in your assigned areas",
        )

    # Update fields
    if device_update.is_active is not None:
        device.is_active = device_update.is_active

    db.commit()
    db.refresh(device)

    logger.info(f"Updated device {device_id} by user {current_user.id}")

    return DeviceResponse(
        id=device.id,
        user_id=device.user_id,
        administrative_id=device.administrative_id,
        push_token=device.push_token,
        app_version=device.app_version,
        is_active=device.is_active,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deactivate all devices for the current user.

    Called when user logs out to prevent notifications to inactive sessions.
    Devices are not deleted, just marked as inactive.
    They will be reactivated on next login.
    """
    try:
        # Deactivate all devices for this user
        updated_count = (
            db.query(Device)
            .filter(
                Device.user_id == current_user.id,
                Device.is_active == True,  # noqa: E712
            )
            .update({"is_active": False})
        )

        db.commit()

        logger.info(
            f"Deactivated {updated_count} device(s) for user {current_user.id}"
        )

        return {
            "success": True,
            "deactivated_count": updated_count,
            "message": f"Deactivated {updated_count} device(s)",
        }

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error deactivating devices for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate devices",
        )


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a device registration.

    Users can only delete devices in their assigned administrative areas.
    This will stop all push notifications to this device.
    """
    device = db.query(Device).filter(Device.id == device_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check if user has access to this administrative area
    user_admin = (
        db.query(UserAdministrative)
        .filter(
            UserAdministrative.user_id == current_user.id,
            UserAdministrative.administrative_id == device.administrative_id,
        )
        .first()
    )

    if not user_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete devices in your assigned areas",
        )

    db.delete(device)
    db.commit()

    logger.info(f"Deleted device {device_id} by user {current_user.id}")

    return None
