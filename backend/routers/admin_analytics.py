"""
Admin Analytics Router for ticket tag statistics and crop distribution.

Provides endpoints for viewing ticket classification analytics
and farmer crop distribution data.
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from config import settings
from database import get_db
from models.ticket import Ticket, TicketTag
from models.user import User, UserType
from models.customer import Customer, OnboardingStatus
from models.administrative import (
    Administrative,
    AdministrativeLevel,
    CustomerAdministrative,
    UserAdministrative,
)
from utils.auth_dependencies import get_current_user
from services.tagging_service import get_all_tags
from services.administrative_service import AdministrativeService

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


@router.get("/statistic-api-token")
async def get_statistic_api_token(
    current_user: User = Depends(get_current_user),
):
    """
    Get the Statistics API token for external applications.

    Only accessible by admin users. Returns the token value
    for use in external dashboards (e.g., Streamlit).
    """
    if current_user.user_type != UserType.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access this endpoint",
        )

    token = settings.statistic_api_token

    if not token:
        return {
            "configured": False,
            "token": None,
            "description": (
                "Statistics API token is not configured. "
                "Set STATISTIC_API_TOKEN in the environment variables."
            ),
        }

    return {
        "configured": True,
        "token": token,
        "description": (
            "Use this token in the Authorization header as: "
            "Bearer <token>"
        ),
    }


def _get_user_customer_ids(
    user: User, db: Session
) -> Optional[List[int]]:
    """
    Get customer IDs accessible by the user based on their
    administrative area assignment.
    """
    if user.user_type == UserType.ADMIN:
        return None  # Admin can access all

    # Get user's administrative areas
    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )

    if not user_admins:
        return []

    # Get all ward IDs under user's assigned areas
    all_ward_ids = set()
    for ua in user_admins:
        ward_ids = AdministrativeService.get_descendant_ward_ids(
            db, ua.administrative_id
        )
        if ward_ids:
            all_ward_ids.update(ward_ids)
        else:
            # If no descendants, it might be a ward itself
            all_ward_ids.add(ua.administrative_id)

    # Get customer IDs in these wards
    customer_ids = [
        ca.customer_id
        for ca in db.query(CustomerAdministrative)
        .filter(CustomerAdministrative.administrative_id.in_(all_ward_ids))
        .all()
    ]

    return customer_ids


@router.get("/crop-distribution")
async def get_crop_distribution(
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
    Get farmer count per crop type.

    Returns data suitable for a horizontal bar chart (X: count, Y: crop).
    Admin users see all data, EO users see only their areas.

    Query parameters:
    - start_date: Filter customers created on or after this date
    - end_date: Filter customers created on or before this date
    """
    # Get crop type column
    crop_type_col = Customer.profile_data.op("->>")("crop_type")

    # Base query: count farmers by crop type
    query = db.query(
        crop_type_col.label("crop"),
        func.count(Customer.id).label("count"),
    ).filter(
        Customer.onboarding_status == OnboardingStatus.COMPLETED,
        crop_type_col.isnot(None),
        crop_type_col != "",
    )

    # Filter by user's administrative area
    customer_ids = _get_user_customer_ids(current_user, db)
    if customer_ids is not None:
        if not customer_ids:
            return {
                "crops": [],
                "total": 0,
                "filters": {
                    "start_date": start_date,
                    "end_date": end_date,
                },
            }
        query = query.filter(Customer.id.in_(customer_ids))

    # Apply date filters
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Customer.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Customer.created_at <= end_dt)
        except ValueError:
            pass

    # Group by crop type and execute
    results = query.group_by(crop_type_col).order_by(
        func.count(Customer.id).desc()
    ).all()

    # Build response
    crops = []
    total = 0
    for crop, count in results:
        crops.append({"crop": crop, "count": count})
        total += count

    return {
        "crops": crops,
        "total": total,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
        },
    }


@router.get("/crop-distribution/matrix")
async def get_crop_distribution_matrix(
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
    Get crop distribution matrix by county (district level).

    Returns data suitable for a matrix table (Rows: County, Columns: Crop).
    Admin users see all data, EO users see only their areas.

    Query parameters:
    - start_date: Filter customers created on or after this date
    - end_date: Filter customers created on or before this date
    """
    crop_type_col = Customer.profile_data.op("->>")("crop_type")

    # Get district level
    district_level = (
        db.query(AdministrativeLevel)
        .filter(AdministrativeLevel.name == "district")
        .first()
    )

    if not district_level:
        return {
            "matrix": [],
            "crop_types": [],
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
            },
        }

    # Get user's accessible customer IDs
    accessible_customer_ids = _get_user_customer_ids(current_user, db)

    # Get all districts
    districts = (
        db.query(Administrative)
        .filter(Administrative.level_id == district_level.id)
        .order_by(Administrative.name)
        .all()
    )

    # Collect all crop types for columns
    all_crop_types = set()
    matrix_data = []

    for district in districts:
        # Get ward IDs under this district
        ward_ids = AdministrativeService.get_descendant_ward_ids(
            db, district.id
        )
        if not ward_ids:
            ward_ids = [district.id]

        # Get customer IDs in these wards
        customer_query = (
            db.query(Customer.id)
            .join(CustomerAdministrative)
            .filter(
                CustomerAdministrative.administrative_id.in_(ward_ids),
                Customer.onboarding_status == OnboardingStatus.COMPLETED,
            )
        )

        # Filter by user's accessible customers
        if accessible_customer_ids is not None:
            if not accessible_customer_ids:
                continue
            customer_query = customer_query.filter(
                Customer.id.in_(accessible_customer_ids)
            )

        # Apply date filters
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                customer_query = customer_query.filter(
                    Customer.created_at >= start_dt
                )
            except ValueError:
                pass

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                customer_query = customer_query.filter(
                    Customer.created_at <= end_dt
                )
            except ValueError:
                pass

        customer_ids = [c.id for c in customer_query.all()]

        if not customer_ids:
            continue

        # Count farmers by crop type in this district
        crop_counts_query = (
            db.query(
                crop_type_col.label("crop"),
                func.count(Customer.id).label("count"),
            )
            .filter(
                Customer.id.in_(customer_ids),
                crop_type_col.isnot(None),
                crop_type_col != "",
            )
            .group_by(crop_type_col)
        )

        crop_counts = {}
        total_in_district = 0
        for crop, count in crop_counts_query.all():
            crop_counts[crop] = count
            total_in_district += count
            all_crop_types.add(crop)

        if total_in_district > 0:
            matrix_data.append({
                "county": district.name,
                "county_id": district.id,
                "crops": crop_counts,
                "total": total_in_district,
            })

    # Sort crop types alphabetically
    sorted_crop_types = sorted(list(all_crop_types))

    return {
        "matrix": matrix_data,
        "crop_types": sorted_crop_types,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
        },
    }
