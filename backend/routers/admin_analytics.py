"""
Admin Analytics Router for ticket tag statistics.

Provides endpoints for viewing ticket classification analytics.
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.ticket import Ticket, TicketTag
from models.user import User, UserType
from models.administrative import UserAdministrative
from utils.auth_dependencies import get_current_user
from services.tagging_service import get_all_tags

router = APIRouter(
    prefix="/admin/analytics",
    tags=["admin-analytics"],
)


def _get_user_administrative_ids(
    user: User, db: Session
) -> Optional[List[int]]:
    """Get list of administrative IDs accessible by the user."""
    if user.user_type == UserType.ADMIN:
        return None  # Admin can access all

    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )
    return [ua.administrative_id for ua in user_admins]


@router.get("/ticket-tags")
async def get_ticket_tag_statistics(
    start_date: Optional[str] = Query(
        None, description="Filter start date (ISO 8601)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter end date (ISO 8601)"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get ticket tag statistics for analytics.

    Returns count of tickets per tag category.
    Admin users see all tickets, EO users see only their areas.

    Query parameters:
    - start_date: Filter tickets resolved on or after this date
    - end_date: Filter tickets resolved on or before this date
    """
    # Base query for resolved tickets with tags
    query = db.query(
        Ticket.tag,
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.resolved_at.isnot(None),
        Ticket.tag.isnot(None),
    )

    # Filter by administrative area for non-admin users
    admin_ids = _get_user_administrative_ids(current_user, db)
    if admin_ids is not None:
        query = query.filter(Ticket.administrative_id.in_(admin_ids))

    # Apply date filters
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Ticket.resolved_at >= start_dt)
        except ValueError:
            pass  # Ignore invalid date format

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Ticket.resolved_at <= end_dt)
        except ValueError:
            pass  # Ignore invalid date format

    # Group by tag and execute
    results = query.group_by(Ticket.tag).all()

    # Build response with all tags (including zero counts)
    tag_counts = {tag.value: 0 for tag in TicketTag}
    for tag_value, count in results:
        if tag_value in tag_counts:
            tag_counts[tag_value] = count

    # Convert to response format
    statistics = []
    total_tagged = 0
    for tag in TicketTag:
        count = tag_counts[tag.value]
        total_tagged += count
        statistics.append({
            "tag": tag.name.lower(),
            "tag_id": tag.value,
            "count": count,
        })

    # Get total resolved tickets (including untagged)
    total_resolved_query = db.query(func.count(Ticket.id)).filter(
        Ticket.resolved_at.isnot(None)
    )
    if admin_ids is not None:
        total_resolved_query = total_resolved_query.filter(
            Ticket.administrative_id.in_(admin_ids)
        )
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            total_resolved_query = total_resolved_query.filter(
                Ticket.resolved_at >= start_dt
            )
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            total_resolved_query = total_resolved_query.filter(
                Ticket.resolved_at <= end_dt
            )
        except ValueError:
            pass

    total_resolved = total_resolved_query.scalar() or 0
    untagged_count = total_resolved - total_tagged

    return {
        "statistics": statistics,
        "total_tagged": total_tagged,
        "total_resolved": total_resolved,
        "untagged_count": untagged_count,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
        },
    }


@router.get("/ticket-tags/available")
async def get_available_tags(
    current_user: User = Depends(get_current_user),
):
    """
    Get list of available ticket tags with descriptions.

    Returns all tag categories that can be used for classification.
    """
    return {
        "tags": get_all_tags(),
    }
