import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, distinct

from database import get_db
from models.message import Message, MessageFrom
from models.ticket import Ticket
from models.user import User
from utils.auth_dependencies import get_current_user

router = APIRouter(prefix="/user", tags=["user-stats"])
logger = logging.getLogger(__name__)


def _get_week_start() -> datetime:
    """Get the start of the current week (Monday 00:00:00 UTC)."""
    now = datetime.now(timezone.utc)
    days_since_monday = now.weekday()
    week_start = now - timedelta(days=days_since_monday)
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)


def _get_month_start() -> datetime:
    """Get the start of the current month (1st day 00:00:00 UTC)."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/stats")
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user statistics for the current user.

    Returns:
        - farmers_reached: Unique customers the EO has messaged
        - conversations_resolved: Tickets resolved by the EO
        - messages_sent: Messages sent by the EO

    Each metric includes this_week, this_month, and all_time counts.
    """
    user_id = current_user.id
    week_start = _get_week_start()
    month_start = _get_month_start()

    # Farmers Reached - unique customers the EO has messaged
    farmers_result = db.query(
        func.count(
            distinct(
                case(
                    (Message.created_at >= week_start, Message.customer_id),
                    else_=None,
                )
            )
        ).label("this_week"),
        func.count(
            distinct(
                case(
                    (Message.created_at >= month_start, Message.customer_id),
                    else_=None,
                )
            )
        ).label("this_month"),
        func.count(distinct(Message.customer_id)).label("all_time"),
    ).filter(
        Message.user_id == user_id,
        Message.from_source == MessageFrom.USER,
    ).first()

    # Conversations Resolved
    resolved_result = db.query(
        func.count(
            case(
                (Ticket.resolved_at >= week_start, 1),
                else_=None,
            )
        ).label("this_week"),
        func.count(
            case(
                (Ticket.resolved_at >= month_start, 1),
                else_=None,
            )
        ).label("this_month"),
        func.count(Ticket.id).label("all_time"),
    ).filter(
        Ticket.resolved_by == user_id,
        Ticket.resolved_at.isnot(None),
    ).first()

    # Messages Sent
    messages_result = db.query(
        func.count(
            case(
                (Message.created_at >= week_start, 1),
                else_=None,
            )
        ).label("this_week"),
        func.count(
            case(
                (Message.created_at >= month_start, 1),
                else_=None,
            )
        ).label("this_month"),
        func.count(Message.id).label("all_time"),
    ).filter(
        Message.user_id == user_id,
        Message.from_source == MessageFrom.USER,
    ).first()

    return {
        "farmers_reached": {
            "this_week": farmers_result.this_week or 0,
            "this_month": farmers_result.this_month or 0,
            "all_time": farmers_result.all_time or 0,
        },
        "conversations_resolved": {
            "this_week": resolved_result.this_week or 0,
            "this_month": resolved_result.this_month or 0,
            "all_time": resolved_result.all_time or 0,
        },
        "messages_sent": {
            "this_week": messages_result.this_week or 0,
            "this_month": messages_result.this_month or 0,
            "all_time": messages_result.all_time or 0,
        },
    }
