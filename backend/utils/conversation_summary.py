"""
Conversation Summary Utility

Reusable utility to merge farmer questions (before + after FOLLOW_UP messages)
and export with customer context.

GitHub Issue: https://github.com/akvo/agriconnect/issues/137
"""

from datetime import timedelta
from typing import List, Optional

import pandas as pd
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models.administrative import Administrative, CustomerAdministrative
from models.customer import Customer
from models.message import Message, MessageFrom
from schemas.callback import MessageType


def get_customer_context(db: Session, customer_id: int) -> dict:
    """
    Get customer context for data governance compliant export.

    Args:
        db: Database session
        customer_id: Customer ID

    Returns:
        dict with farmer_id, ward, crop, gender, age_group
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return {
            "farmer_id": customer_id,
            "ward": None,
            "crop": None,
            "gender": None,
            "age_group": None,
        }

    # Get ward name from customer_administrative -> administrative.name
    ward = None
    customer_admin = (
        db.query(CustomerAdministrative)
        .filter(CustomerAdministrative.customer_id == customer_id)
        .first()
    )
    if customer_admin:
        admin = (
            db.query(Administrative)
            .filter(Administrative.id == customer_admin.administrative_id)
            .first()
        )
        if admin:
            ward = admin.name

    # Get crop from profile_data
    crop = None
    if customer.profile_data:
        crop = customer.profile_data.get("crop_type")

    return {
        "farmer_id": customer_id,
        "ward": ward,
        "crop": crop,
        "gender": customer.gender,
        "age_group": customer.age_group,
    }


def merge_questions(
    before_msg: Optional[Message],
    after_msg: Optional[Message]
) -> str:
    """
    Merge two messages into a single question string.

    Args:
        before_msg: Message before FOLLOW_UP (can be None)
        after_msg: Message after FOLLOW_UP (can be None)

    Returns:
        Merged question string
    """
    parts = []

    if before_msg and before_msg.body:
        parts.append(before_msg.body.strip())

    if after_msg and after_msg.body:
        parts.append(after_msg.body.strip())

    return ". ".join(parts) if parts else ""


def get_follow_up_conversations(
    db: Session,
    time_threshold_minutes: int = 5
) -> pd.DataFrame:
    """
    Get all conversations with FOLLOW_UP messages,
    merging questions before and after the follow-up.

    Args:
        db: Database session
        time_threshold_minutes: Max time gap for merging messages (default: 5)

    Returns:
        DataFrame with columns: farmer_id, ward, crop, gender,
        age_group, query_text, date
    """
    # Query all FOLLOW_UP messages
    follow_up_messages = (
        db.query(Message)
        .filter(Message.message_type == MessageType.FOLLOW_UP)
        .order_by(Message.created_at)
        .all()
    )

    results: List[dict] = []
    threshold = timedelta(minutes=time_threshold_minutes)

    for follow_up in follow_up_messages:
        customer_id = follow_up.customer_id
        follow_up_time = follow_up.created_at

        # Find customer message BEFORE the follow-up
        # (from_source=1 means CUSTOMER, within threshold)
        before_msg = (
            db.query(Message)
            .filter(
                and_(
                    Message.customer_id == customer_id,
                    Message.from_source == MessageFrom.CUSTOMER,
                    Message.created_at < follow_up_time,
                    Message.created_at >= follow_up_time - threshold,
                    # Handle NULL message_type (NULL != value is NULL in SQL)
                    or_(
                        Message.message_type != MessageType.FOLLOW_UP,
                        Message.message_type.is_(None),
                    ),
                )
            )
            .order_by(Message.created_at.desc())
            .first()
        )

        # Find customer message AFTER the follow-up
        # (from_source=1 means CUSTOMER, within threshold)
        after_msg = (
            db.query(Message)
            .filter(
                and_(
                    Message.customer_id == customer_id,
                    Message.from_source == MessageFrom.CUSTOMER,
                    Message.created_at > follow_up_time,
                    Message.created_at <= follow_up_time + threshold,
                    # Handle NULL message_type (NULL != value is NULL in SQL)
                    or_(
                        Message.message_type != MessageType.FOLLOW_UP,
                        Message.message_type.is_(None),
                    ),
                )
            )
            .order_by(Message.created_at)
            .first()
        )

        # Skip if no messages found
        if not before_msg and not after_msg:
            continue

        # Merge questions
        merged_question = merge_questions(before_msg, after_msg)

        if not merged_question:
            continue

        # Get customer context
        context = get_customer_context(db, customer_id)

        # Determine date (use earliest message time)
        if before_msg:
            date = before_msg.created_at
        else:
            date = after_msg.created_at

        results.append({
            "farmer_id": context["farmer_id"],
            "ward": context["ward"],
            "crop": context["crop"],
            "gender": context["gender"],
            "age_group": context["age_group"],
            "query_text": merged_question,
            "date": date,
        })

    # Create DataFrame
    df = pd.DataFrame(results)

    # Ensure columns exist even if empty
    if df.empty:
        df = pd.DataFrame(columns=[
            "farmer_id", "ward", "crop", "gender", "age_group",
            "query_text", "date"
        ])

    return df
