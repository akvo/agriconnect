"""
Statistics API Router.

Provides endpoints for external applications (e.g., Streamlit dashboards)
to access farmer and EO statistics. Authentication via static API token.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.statistic import (
    FarmerStatsResponse,
    FarmerStatsByWardResponse,
    RegistrationChartResponse,
    EOStatsResponse,
    EOStatsByEOResponse,
    EOCountResponse,
    EOListResponse,
    FarmerStatsFilters,
    EOStatsFilters,
    RegistrationFilters,
)
from services.statistic_service import StatisticService
from utils.statistic_auth import verify_statistic_token

router = APIRouter(
    prefix="/statistic",
    tags=["statistics"],
    dependencies=[Depends(verify_statistic_token)],
)


@router.get("/farmers/stats", response_model=FarmerStatsResponse)
async def get_farmer_statistics(
    start_date: Optional[str] = Query(
        None, description="Filter start date (ISO 8601 format)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter end date (ISO 8601 format)"
    ),
    administrative_id: Optional[int] = Query(
        None,
        description="Filter by administrative area ID (region, district, "
        "or ward). Aggregates data from all descendant areas."
    ),
    phone_prefix: Optional[str] = Query(
        None, description="Filter by phone number prefix (e.g., '+254')"
    ),
    active_days: int = Query(
        30, description="Days to consider a farmer as 'active' (default: 30)"
    ),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive farmer statistics.

    Returns onboarding progress, activity metrics, feature usage,
    and escalation statistics.

    The administrative_id parameter accepts any administrative level:
    - Region ID: Aggregates stats from all districts and wards in the region
    - District ID: Aggregates stats from all wards in the district
    - Ward ID: Returns stats for that specific ward

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    stats = service.get_farmer_stats(
        start_date=start_date,
        end_date=end_date,
        administrative_id=administrative_id,
        phone_prefix=phone_prefix,
        active_days=active_days,
    )

    return FarmerStatsResponse(
        onboarding=stats["onboarding"],
        activity=stats["activity"],
        features=stats["features"],
        escalations=stats["escalations"],
        filters=FarmerStatsFilters(
            start_date=start_date,
            end_date=end_date,
            administrative_id=administrative_id,
            phone_prefix=phone_prefix,
            active_days=active_days,
        ),
    )


@router.get("/farmers/stats/by-ward", response_model=FarmerStatsByWardResponse)
async def get_farmer_statistics_by_ward(
    start_date: Optional[str] = Query(
        None, description="Filter start date (ISO 8601 format)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter end date (ISO 8601 format)"
    ),
    administrative_id: Optional[int] = Query(
        None,
        description="Filter to wards under this administrative area. "
        "If region/district ID, shows all wards under that area."
    ),
    phone_prefix: Optional[str] = Query(
        None, description="Filter by phone number prefix (e.g., '+254')"
    ),
    db: Session = Depends(get_db),
):
    """
    Get farmer statistics grouped by ward.

    Returns registration, question, and escalation counts per ward.

    The administrative_id parameter filters which wards are included:
    - Region ID: Returns stats for all wards in the region
    - District ID: Returns stats for all wards in the district
    - Ward ID: Returns stats for that specific ward only

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    data = service.get_farmer_stats_by_ward(
        start_date=start_date,
        end_date=end_date,
        phone_prefix=phone_prefix,
        administrative_id=administrative_id,
    )

    return FarmerStatsByWardResponse(
        data=data,
        filters=FarmerStatsFilters(
            start_date=start_date,
            end_date=end_date,
            administrative_id=administrative_id,
            phone_prefix=phone_prefix,
        ),
    )


@router.get("/farmers/registrations", response_model=RegistrationChartResponse)
async def get_registration_chart_data(
    start_date: Optional[str] = Query(
        None, description="Filter start date (ISO 8601 format)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter end date (ISO 8601 format)"
    ),
    administrative_id: Optional[int] = Query(
        None,
        description="Filter by administrative area ID (region, district, "
        "or ward). Aggregates data from all descendant areas."
    ),
    phone_prefix: Optional[str] = Query(
        None, description="Filter by phone number prefix (e.g., '+254')"
    ),
    group_by: str = Query(
        "day", description="Group by: 'day', 'week', or 'month'"
    ),
    db: Session = Depends(get_db),
):
    """
    Get registration data for charting.

    Returns time series data of farmer registrations grouped by
    day, week, or month.

    The administrative_id parameter accepts any administrative level:
    - Region ID: Aggregates registrations from all wards in the region
    - District ID: Aggregates registrations from all wards in the district
    - Ward ID: Returns registrations for that specific ward

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    # Validate group_by
    if group_by not in ("day", "week", "month"):
        group_by = "day"

    service = StatisticService(db)
    data, total = service.get_registration_chart_data(
        start_date=start_date,
        end_date=end_date,
        administrative_id=administrative_id,
        phone_prefix=phone_prefix,
        group_by=group_by,
    )

    return RegistrationChartResponse(
        data=data,
        total=total,
        filters=RegistrationFilters(
            start_date=start_date,
            end_date=end_date,
            administrative_id=administrative_id,
            phone_prefix=phone_prefix,
            group_by=group_by,
        ),
    )


@router.get("/eo/stats", response_model=EOStatsResponse)
async def get_eo_statistics(
    start_date: Optional[str] = Query(
        None, description="Filter start date (ISO 8601 format)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter end date (ISO 8601 format)"
    ),
    eo_id: Optional[int] = Query(
        None, description="Filter by specific EO ID"
    ),
    administrative_id: Optional[int] = Query(
        None,
        description="Filter by administrative area ID. Filters tickets "
        "by customers in that area."
    ),
    db: Session = Depends(get_db),
):
    """
    Get EO (Extension Officer) statistics.

    Returns ticket handling metrics and bulk message counts.

    The administrative_id parameter filters tickets by customer location:
    - Region ID: Includes tickets from customers in all wards of the region
    - District ID: Includes tickets from customers in all wards of the district
    - Ward ID: Includes tickets from customers in that specific ward

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    stats = service.get_eo_stats(
        start_date=start_date,
        end_date=end_date,
        eo_id=eo_id,
        administrative_id=administrative_id,
    )

    return EOStatsResponse(
        tickets=stats["tickets"],
        messages=stats["messages"],
        filters=EOStatsFilters(
            start_date=start_date,
            end_date=end_date,
            eo_id=eo_id,
            administrative_id=administrative_id,
        ),
    )


@router.get("/eo/stats/by-eo", response_model=EOStatsByEOResponse)
async def get_eo_statistics_by_eo(
    start_date: Optional[str] = Query(
        None, description="Filter start date (ISO 8601 format)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter end date (ISO 8601 format)"
    ),
    administrative_id: Optional[int] = Query(
        None,
        description="Filter to EOs assigned to this area or its "
        "descendant areas."
    ),
    db: Session = Depends(get_db),
):
    """
    Get EO statistics grouped by individual EO.

    Returns reply counts and tickets closed per EO.

    The administrative_id parameter filters which EOs are included:
    - Region ID: Returns stats for EOs assigned to that region or any
      district/ward within it
    - District ID: Returns stats for EOs assigned to that district or any
      ward within it
    - Ward ID: Returns stats for EOs assigned to that specific ward

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    data = service.get_eo_stats_by_eo(
        start_date=start_date,
        end_date=end_date,
        administrative_id=administrative_id,
    )

    return EOStatsByEOResponse(
        data=data,
        filters=EOStatsFilters(
            start_date=start_date,
            end_date=end_date,
            administrative_id=administrative_id,
        ),
    )


@router.get("/eo/count", response_model=EOCountResponse)
async def get_eo_count(
    administrative_id: Optional[int] = Query(
        None,
        description="Filter to EOs in this administrative area. "
        "Works with any level (region, district, ward)."
    ),
    db: Session = Depends(get_db),
):
    """
    Get count of active EOs.

    Returns the total number of active Extension Officers.

    The administrative_id parameter filters by area:
    - No filter: Returns total count of all active EOs
    - Region ID: Returns count of EOs in that region (includes districts/wards)
    - District ID: Returns count of EOs in that district (includes wards)
    - Ward ID: Returns count of EOs assigned to that specific ward

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    count = service.get_eo_count(administrative_id=administrative_id)

    return EOCountResponse(
        count=count,
        administrative_id=administrative_id,
    )


@router.get("/eo/list", response_model=EOListResponse)
async def get_eo_list(
    db: Session = Depends(get_db),
):
    """
    Get list of all active EOs for filter dropdown.

    Returns EO IDs and names sorted alphabetically.

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    data = service.get_eo_list()

    return EOListResponse(data=data)
