"""
Device registration router for push notifications.

Implements device registration and management endpoints
for Expo push notifications.
"""

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import get_db
from models.device import Device
from models.user import User
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

    - If push_token already exists for this user, update it (upsert behavior)
    - If push_token exists for a different user, return 409 conflict
    - Updates last_seen_at on every registration
    """
    try:
        # Check if this push token already exists
        existing_device = (
            db.query(Device)
            .filter(Device.push_token == device_data.push_token)
            .first()
        )

        if existing_device:
            # If token belongs to current user, update it
            if existing_device.user_id == current_user.id:
                existing_device.platform = device_data.platform
                existing_device.app_version = device_data.app_version
                existing_device.is_active = True
                existing_device.last_seen_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(existing_device)

                logger.info(
                    f"Updated device {existing_device.id} "
                    f"for user {current_user.id}"
                )

                return DeviceResponse(
                    id=existing_device.id,
                    user_id=existing_device.user_id,
                    push_token=existing_device.push_token,
                    platform=existing_device.platform.value,
                    app_version=existing_device.app_version,
                    is_active=existing_device.is_active,
                    last_seen_at=existing_device.last_seen_at,
                    created_at=existing_device.created_at,
                    updated_at=existing_device.updated_at,
                )
            else:
                # Token belongs to different user - conflict
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Push token already registered to another user",
                )

        # Create new device registration
        new_device = Device(
            user_id=current_user.id,
            push_token=device_data.push_token,
            platform=device_data.platform,
            app_version=device_data.app_version,
            is_active=True,
            last_seen_at=datetime.now(timezone.utc),
        )

        db.add(new_device)
        db.commit()
        db.refresh(new_device)

        logger.info(
            f"Registered new device {new_device.id} "
            f"for user {current_user.id}"
        )

        return DeviceResponse(
            id=new_device.id,
            user_id=new_device.user_id,
            push_token=new_device.push_token,
            platform=new_device.platform.value,
            app_version=new_device.app_version,
            is_active=new_device.is_active,
            last_seen_at=new_device.last_seen_at,
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
    List all devices registered for the current user.

    Returns both active and inactive devices.
    """
    devices = (
        db.query(Device)
        .filter(Device.user_id == current_user.id)
        .order_by(Device.last_seen_at.desc())
        .all()
    )

    return [
        DeviceResponse(
            id=device.id,
            user_id=device.user_id,
            push_token=device.push_token,
            platform=device.platform.value,
            app_version=device.app_version,
            is_active=device.is_active,
            last_seen_at=device.last_seen_at,
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

    Users can only update their own devices.
    """
    device = db.query(Device).filter(Device.id == device_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check ownership
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own devices",
        )

    # Update fields
    if device_update.is_active is not None:
        device.is_active = device_update.is_active

    db.commit()
    db.refresh(device)

    logger.info(f"Updated device {device_id} for user {current_user.id}")

    return DeviceResponse(
        id=device.id,
        user_id=device.user_id,
        push_token=device.push_token,
        platform=device.platform.value,
        app_version=device.app_version,
        is_active=device.is_active,
        last_seen_at=device.last_seen_at,
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

    Users can only delete their own devices.
    This will stop all push notifications to this device.
    """
    device = db.query(Device).filter(Device.id == device_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check ownership
    if device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own devices",
        )

    db.delete(device)
    db.commit()

    logger.info(f"Deleted device {device_id} for user {current_user.id}")

    return None
