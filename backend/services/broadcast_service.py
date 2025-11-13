"""
Broadcast service for managing broadcast groups and messages.

Part 2: Integrated with Celery for async message processing.
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, distinct

from models.broadcast import (
    BroadcastGroup,
    BroadcastGroupContact,
    BroadcastMessage,
    BroadcastMessageGroup,
    BroadcastRecipient,
)
from models.message import DeliveryStatus
from models.customer import Customer
from tasks.broadcast_tasks import process_broadcast

logger = logging.getLogger(__name__)


class BroadcastService:
    def __init__(self, db: Session):
        self.db = db

    # ========== Broadcast Group Management ==========

    def create_group(
        self,
        name: str,
        customer_ids: List[int],
        created_by: int,
        administrative_id: Optional[int] = None
    ) -> BroadcastGroup:
        """
        Create a new broadcast group with selected customer IDs.
        crop_types and age_groups are derived from group members.
        """
        group = BroadcastGroup(
            name=name,
            administrative_id=administrative_id,
            created_by=created_by
        )
        self.db.add(group)
        self.db.flush()

        # Add selected contacts
        for customer_id in customer_ids:
            contact = BroadcastGroupContact(
                broadcast_group_id=group.id,
                customer_id=customer_id
            )
            self.db.add(contact)

        self.db.commit()
        self.db.refresh(group)

        logger.info(
            f"Created broadcast group '{name}' (id={group.id}) "
            f"with {len(customer_ids)} contacts"
        )

        return group

    def get_all_groups(self) -> List[BroadcastGroup]:
        """Get all broadcast groups (for admin users)."""
        return self.db.query(BroadcastGroup).order_by(
            BroadcastGroup.created_at.desc()
        ).all()

    def get_groups_for_eo(
        self,
        eo_id: int,
        administrative_id: Optional[int] = None
    ) -> List[BroadcastGroup]:
        """Get all broadcast groups visible to an EO."""
        query = self.db.query(BroadcastGroup)

        if administrative_id:
            # Show groups in same ward
            query = query.filter(
                BroadcastGroup.administrative_id == administrative_id
            )
        else:
            # Show only groups created by this EO
            query = query.filter(BroadcastGroup.created_by == eo_id)

        return query.order_by(BroadcastGroup.created_at.desc()).all()

    def get_group_by_id(
        self,
        group_id: int,
        eo_id: int,
        administrative_id: Optional[int] = None,
        is_admin: bool = False
    ) -> Optional[BroadcastGroup]:
        """Get broadcast group by ID with ward access validation."""
        query = self.db.query(BroadcastGroup).filter(
            BroadcastGroup.id == group_id
        )

        # Admin can access all groups
        if is_admin:
            return query.first()

        if administrative_id:
            query = query.filter(
                BroadcastGroup.administrative_id == administrative_id
            )
        else:
            query = query.filter(BroadcastGroup.created_by == eo_id)

        return query.first()

    def update_group(
        self,
        group_id: int,
        eo_id: int,
        name: Optional[str] = None,
        customer_ids: Optional[List[int]] = None,
        administrative_id: Optional[int] = None
    ) -> Optional[BroadcastGroup]:
        """Update broadcast group (only if EO is owner)."""
        group = self.get_group_by_id(group_id, eo_id, administrative_id)
        if not group:
            return None

        # Only owner can update
        if group.created_by != eo_id:
            logger.warning(
                f"EO {eo_id} attempted to update group {group_id} "
                f"owned by {group.created_by}"
            )
            return None

        # Update name if provided
        if name is not None:
            group.name = name

        # Update contacts if provided
        if customer_ids is not None:
            self.db.query(BroadcastGroupContact).filter(
                BroadcastGroupContact.broadcast_group_id == group_id
            ).delete()

            for customer_id in customer_ids:
                contact = BroadcastGroupContact(
                    broadcast_group_id=group_id,
                    customer_id=customer_id
                )
                self.db.add(contact)

        self.db.commit()
        self.db.refresh(group)

        logger.info(f"Updated broadcast group {group_id}")
        return group

    def delete_group(
        self,
        group_id: int,
        eo_id: int,
        administrative_id: Optional[int] = None
    ) -> bool:
        """Delete broadcast group (only if EO is owner)."""
        group = self.get_group_by_id(group_id, eo_id, administrative_id)
        if not group:
            return False

        # Only owner can delete
        if group.created_by != eo_id:
            logger.warning(
                f"EO {eo_id} attempted to delete group {group_id} "
                f"owned by {group.created_by}"
            )
            return False

        self.db.delete(group)
        self.db.commit()

        logger.info(f"Deleted broadcast group {group_id}")
        return True

    # ========== Broadcast Message Creation ==========

    def create_broadcast(
        self,
        message: str,
        group_ids: List[int],
        created_by: int,
        administrative_id: Optional[int] = None,
        is_admin: bool = False
    ) -> Optional[BroadcastMessage]:
        """
        Create broadcast message and queue Celery task for async processing.

        Part 2: Integrated with Celery - broadcasts are queued for processing.
        """
        # Validate access to all groups
        for group_id in group_ids:
            group = self.get_group_by_id(
                group_id, created_by, administrative_id, is_admin
            )
            if not group:
                logger.error(f"Group {group_id} not accessible")
                return None

        # Get all unique recipients across all groups
        recipients = (
            self.db.query(
                distinct(BroadcastGroupContact.customer_id),
                Customer.phone_number,
                Customer.full_name
            )
            .join(
                Customer,
                Customer.id == BroadcastGroupContact.customer_id
            )
            .filter(BroadcastGroupContact.broadcast_group_id.in_(group_ids))
            .all()
        )

        if not recipients:
            logger.error(f"No recipients found for groups {group_ids}")
            return None

        # Create BroadcastMessage with 'queued' status
        broadcast = BroadcastMessage(
            message=message,
            created_by=created_by,
            status='queued'
        )
        self.db.add(broadcast)
        self.db.flush()

        # Link to groups (many-to-many)
        for group_id in group_ids:
            link = BroadcastMessageGroup(
                broadcast_message_id=broadcast.id,
                broadcast_group_id=group_id
            )
            self.db.add(link)

        # Create BroadcastRecipient entries for delivery tracking
        for customer_id, phone, name in recipients:
            contact = BroadcastRecipient(
                broadcast_message_id=broadcast.id,
                customer_id=customer_id,
                status=DeliveryStatus.PENDING
            )
            self.db.add(contact)

        self.db.commit()
        self.db.refresh(broadcast)

        # Queue Celery task for async processing
        try:
            task = process_broadcast.delay(broadcast.id)
            logger.info(
                f"Broadcast {broadcast.id} queued with "
                f"{len(recipients)} recipients (task_id={task.id})"
            )
        except Exception as e:
            logger.error(
                f"Failed to queue broadcast {broadcast.id}: {e}"
            )
            # Update status to failed if queuing fails
            broadcast.status = 'failed'
            self.db.commit()
            return None

        return broadcast

    def get_broadcast_status(
        self,
        broadcast_id: int,
        created_by: int
    ) -> Optional[BroadcastMessage]:
        """Get broadcast message with status."""
        broadcast = (
            self.db.query(BroadcastMessage)
            .filter(
                and_(
                    BroadcastMessage.id == broadcast_id,
                    BroadcastMessage.created_by == created_by
                )
            )
            .first()
        )

        return broadcast

    def get_broadcasts_by_group(
        self,
        group_id: int,
        eo_id: int,
        administrative_id: Optional[int] = None,
        is_admin: bool = False
    ) -> Optional[List[BroadcastMessage]]:
        """
        Get all broadcast messages for a specific group.
        Returns broadcasts in reverse chronological order.
        Returns None if group not found or user doesn't have access.
        """
        # First verify the user has access to this group
        group = self.get_group_by_id(
            group_id=group_id,
            eo_id=eo_id,
            administrative_id=administrative_id,
            is_admin=is_admin
        )

        if not group:
            return None

        # Get all broadcasts that target this group
        broadcasts = (
            self.db.query(BroadcastMessage)
            .join(BroadcastMessageGroup)
            .filter(BroadcastMessageGroup.broadcast_group_id == group_id)
            .order_by(BroadcastMessage.created_at.asc())
            .all()
        )

        return broadcasts


def get_broadcast_service(db: Session) -> BroadcastService:
    """Get BroadcastService instance"""
    return BroadcastService(db)
