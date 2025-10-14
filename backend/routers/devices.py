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
from models.user import User
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

    - Devices are associated with administrative areas (wards)
    - If push_token already exists, update it (upsert behavior)
    - Same device can be used by different users in the same ward
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

        if not user_admin:
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
            # Update existing device
            existing_device.administrative_id = device_data.administrative_id
            existing_device.app_version = device_data.app_version
            existing_device.is_active = True
            db.commit()
            db.refresh(existing_device)

            logger.info(
                f"Updated device {existing_device.id} "
                f"for administrative_id {device_data.administrative_id}"
            )

            return DeviceResponse(
                id=existing_device.id,
                administrative_id=existing_device.administrative_id,
                push_token=existing_device.push_token,
                app_version=existing_device.app_version,
                is_active=existing_device.is_active,
                created_at=existing_device.created_at,
                updated_at=existing_device.updated_at,
            )

        # Create new device registration
        new_device = Device(
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
            f"for administrative_id {device_data.administrative_id}"
        )

        return DeviceResponse(
            id=new_device.id,
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

    Returns devices from all wards where the user has access.
    """
    # Get all administrative IDs for current user
    user_admin_ids = (
        db.query(UserAdministrative.administrative_id)
        .filter(UserAdministrative.user_id == current_user.id)
        .all()
    )

    admin_ids = [ua.administrative_id for ua in user_admin_ids]

    if not admin_ids:
        return []

    devices = (
        db.query(Device)
        .filter(Device.administrative_id.in_(admin_ids))
        .order_by(Device.created_at.desc())
        .all()
    )

    return [
        DeviceResponse(
            id=device.id,
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
        administrative_id=device.administrative_id,
        push_token=device.push_token,
        app_version=device.app_version,
        is_active=device.is_active,
        created_at=device.created_at,
        updated_at=device.updated_at,
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
