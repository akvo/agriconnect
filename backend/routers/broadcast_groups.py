"""
Broadcast group management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from utils.auth_dependencies import get_current_user
from models.user import User, UserType
from models.customer import Customer
from models.administrative import UserAdministrative
from services.broadcast_service import get_broadcast_service
from schemas.broadcast import (
    BroadcastGroupCreate,
    BroadcastGroupUpdate,
    BroadcastGroupResponse,
    BroadcastGroupDetail,
    BroadcastGroupContact
)

router = APIRouter(prefix="/broadcast/groups", tags=["Broadcast Groups"])


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
    response_model=BroadcastGroupResponse,
    status_code=status.HTTP_201_CREATED
)
def create_broadcast_group(
    group_data: BroadcastGroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new broadcast group."""
    # Validate customers exist
    customers = db.query(Customer).filter(
        Customer.id.in_(group_data.customer_ids)
    ).all()

    if len(customers) != len(group_data.customer_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more customer IDs not found"
        )

    # Get user's ward
    ward_id = _get_user_ward(current_user, db)

    service = get_broadcast_service(db)
    group = service.create_group(
        name=group_data.name,
        customer_ids=group_data.customer_ids,
        created_by=current_user.id,
        crop_types=group_data.crop_types,
        age_groups=group_data.age_groups,
        administrative_id=ward_id
    )

    return BroadcastGroupResponse(
        id=group.id,
        name=group.name,
        crop_types=group.crop_types,
        age_groups=group.age_groups,
        administrative_id=group.administrative_id,
        created_by=group.created_by,
        contact_count=len(group_data.customer_ids),
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@router.get("", response_model=List[BroadcastGroupResponse])
def list_broadcast_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all broadcast groups visible to current user."""
    service = get_broadcast_service(db)
    # Admin can see all groups
    if current_user.user_type == UserType.ADMIN:
        groups = service.get_all_groups()
    else:
        # EO sees groups in their ward
        ward_id = _get_user_ward(current_user, db)
        groups = service.get_groups_for_eo(
            eo_id=current_user.id,
            administrative_id=ward_id
        )

    result = []
    for group in groups:
        result.append(BroadcastGroupResponse(
            id=group.id,
            name=group.name,
            crop_types=group.crop_types,
            age_groups=group.age_groups,
            administrative_id=group.administrative_id,
            created_by=group.created_by,
            contact_count=len(group.group_contacts),
            created_at=group.created_at,
            updated_at=group.updated_at
        ))

    return result


@router.get("/{group_id}", response_model=BroadcastGroupDetail)
def get_broadcast_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a broadcast group."""
    ward_id = _get_user_ward(current_user, db)

    service = get_broadcast_service(db)
    group = service.get_group_by_id(
        group_id=group_id,
        eo_id=current_user.id,
        administrative_id=ward_id
    )

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broadcast group not found"
        )

    contacts = [
        BroadcastGroupContact(
            customer_id=c.customer.id,
            phone_number=c.customer.phone_number,
            full_name=c.customer.full_name
        )
        for c in group.group_contacts
    ]

    return BroadcastGroupDetail(
        id=group.id,
        name=group.name,
        crop_types=group.crop_types,
        age_groups=group.age_groups,
        administrative_id=group.administrative_id,
        created_by=group.created_by,
        contacts=contacts,
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@router.patch("/{group_id}", response_model=BroadcastGroupResponse)
def update_broadcast_group(
    group_id: int,
    group_data: BroadcastGroupUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update broadcast group (owner only)."""
    ward_id = _get_user_ward(current_user, db)

    service = get_broadcast_service(db)
    group = service.update_group(
        group_id=group_id,
        eo_id=current_user.id,
        name=group_data.name,
        crop_types=group_data.crop_types,
        age_groups=group_data.age_groups,
        customer_ids=group_data.customer_ids,
        administrative_id=ward_id
    )

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broadcast group not found or not owner"
        )

    return BroadcastGroupResponse(
        id=group.id,
        name=group.name,
        crop_types=group.crop_types,
        age_groups=group.age_groups,
        administrative_id=group.administrative_id,
        created_by=group.created_by,
        contact_count=len(group.group_contacts),
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_broadcast_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete broadcast group (owner only)."""
    ward_id = _get_user_ward(current_user, db)

    service = get_broadcast_service(db)
    deleted = service.delete_group(
        group_id=group_id,
        eo_id=current_user.id,
        administrative_id=ward_id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broadcast group not found or not owner"
        )
