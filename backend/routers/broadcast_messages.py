"""
Broadcast message API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from utils.auth_dependencies import get_current_user
from models.user import User, UserType
from models.administrative import UserAdministrative
from models.message import DeliveryStatus
from services.broadcast_service import get_broadcast_service
from schemas.broadcast import (
    BroadcastMessageCreate,
    BroadcastMessageResponse,
    BroadcastMessageStatus,
    BroadcastRecipientStatus
)

router = APIRouter(
    prefix="/broadcast/messages", tags=["Broadcast Messages"]
)


def _get_user_ward(user: User, db: Session) -> Optional[int]:
    """Get the ward ID for an EO user. Returns None for admins."""
    if user.user_type == UserType.ADMIN:
        # Admins can access all wards
        return None

    # EO should have exactly one administrative area (ward)
    user_admin = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .first()
    )

    return user_admin.administrative_id if user_admin else None


@router.post(
    "",
    response_model=BroadcastMessageResponse,
    status_code=status.HTTP_201_CREATED
)
def create_broadcast(
    message_data: BroadcastMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create and queue a broadcast message (stub for Part 1).

    NOTE: This is Part 1 implementation. Message creation only.
    Celery queue integration will be added in Part 2.
    """
    ward_id = _get_user_ward(current_user, db)
    is_admin = current_user.user_type == UserType.ADMIN

    service = get_broadcast_service(db)
    broadcast = service.create_broadcast(
        message=message_data.message,
        group_ids=message_data.group_ids,
        created_by=current_user.id,
        administrative_id=ward_id,
        is_admin=is_admin
    )

    if not broadcast:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create broadcast. Check group access."
        )

    return BroadcastMessageResponse(
        id=broadcast.id,
        message=broadcast.message,
        status=broadcast.status,
        total_recipients=len(broadcast.broadcast_recipients),
        queued_at=broadcast.queued_at,
        created_at=broadcast.created_at
    )


@router.get("/{broadcast_id}", response_model=BroadcastMessageStatus)
def get_broadcast_status(
    broadcast_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed status of a broadcast including per-contact delivery tracking.
    """
    service = get_broadcast_service(db)
    broadcast = service.get_broadcast_status(
        broadcast_id=broadcast_id,
        created_by=current_user.id
    )

    if not broadcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broadcast not found"
        )

    # Calculate delivery statistics
    sent_count = sum(
        1 for c in broadcast.broadcast_recipients
        if c.status in [
            DeliveryStatus.SENT,
            DeliveryStatus.DELIVERED,
            DeliveryStatus.READ
        ]
    )
    delivered_count = sum(
        1 for c in broadcast.broadcast_recipients
        if c.status in [
            DeliveryStatus.DELIVERED,
            DeliveryStatus.READ
        ]
    )
    failed_count = sum(
        1 for c in broadcast.broadcast_recipients
        if c.status in [
            DeliveryStatus.FAILED,
            DeliveryStatus.UNDELIVERED
        ]
    )

    # Build contact status list
    recipients = [
        BroadcastRecipientStatus(
            customer_id=c.customer.id,
            phone_number=c.customer.phone_number,
            full_name=c.customer.full_name,
            status=c.status,
            sent_at=c.sent_at,
            delivered_at=c.delivered_at,
            error_message=c.error_message
        )
        for c in broadcast.broadcast_recipients
    ]

    return BroadcastMessageStatus(
        id=broadcast.id,
        message=broadcast.message,
        status=broadcast.status,
        total_recipients=len(broadcast.broadcast_recipients),
        sent_count=sent_count,
        delivered_count=delivered_count,
        failed_count=failed_count,
        recipients=recipients,
        created_at=broadcast.created_at,
        updated_at=broadcast.updated_at
    )


@router.get("/group/{group_id}", response_model=List[BroadcastMessageResponse])
def get_group_broadcasts(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all broadcast messages for a specific group.
    Returns broadcasts in reverse chronological order (newest first).
    """
    ward_id = _get_user_ward(current_user, db)
    is_admin = current_user.user_type == UserType.ADMIN

    service = get_broadcast_service(db)
    broadcasts = service.get_broadcasts_by_group(
        group_id=group_id,
        eo_id=current_user.id,
        administrative_id=ward_id,
        is_admin=is_admin
    )

    if broadcasts is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broadcast group not found"
        )

    return [
        BroadcastMessageResponse(
            id=broadcast.id,
            message=broadcast.message,
            status=broadcast.status,
            total_recipients=len(broadcast.broadcast_recipients),
            queued_at=broadcast.queued_at,
            created_at=broadcast.created_at
        )
        for broadcast in broadcasts
    ]
