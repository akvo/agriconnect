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
    EOCountByDistrictResponse,
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
    ward_id: Optional[int] = Query(
        None, description="Filter by specific ward ID"
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

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    stats = service.get_farmer_stats(
        start_date=start_date,
        end_date=end_date,
        ward_id=ward_id,
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
            ward_id=ward_id,
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
    phone_prefix: Optional[str] = Query(
        None, description="Filter by phone number prefix (e.g., '+254')"
    ),
    db: Session = Depends(get_db),
):
    """
    Get farmer statistics grouped by ward.

    Returns registration, question, and escalation counts per ward.

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    data = service.get_farmer_stats_by_ward(
        start_date=start_date,
        end_date=end_date,
        phone_prefix=phone_prefix,
    )

    return FarmerStatsByWardResponse(
        data=data,
        filters=FarmerStatsFilters(
            start_date=start_date,
            end_date=end_date,
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
    ward_id: Optional[int] = Query(
        None, description="Filter by specific ward ID"
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

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    # Validate group_by
    if group_by not in ("day", "week", "month"):
        group_by = "day"

    service = StatisticService(db)
    data, total = service.get_registration_chart_data(
        start_date=start_date,
        end_date=end_date,
        ward_id=ward_id,
        phone_prefix=phone_prefix,
        group_by=group_by,
    )

    return RegistrationChartResponse(
        data=data,
        total=total,
        filters=RegistrationFilters(
            start_date=start_date,
            end_date=end_date,
            ward_id=ward_id,
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
    db: Session = Depends(get_db),
):
    """
    Get EO (Extension Officer) statistics.

    Returns ticket handling metrics and bulk message counts.

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    stats = service.get_eo_stats(
        start_date=start_date,
        end_date=end_date,
        eo_id=eo_id,
    )

    return EOStatsResponse(
        tickets=stats["tickets"],
        messages=stats["messages"],
        filters=EOStatsFilters(
            start_date=start_date,
            end_date=end_date,
            eo_id=eo_id,
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
    db: Session = Depends(get_db),
):
    """
    Get EO statistics grouped by individual EO.

    Returns reply counts and tickets closed per EO.

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    data = service.get_eo_stats_by_eo(
        start_date=start_date,
        end_date=end_date,
    )

    return EOStatsByEOResponse(
        data=data,
        filters=EOStatsFilters(
            start_date=start_date,
            end_date=end_date,
        ),
    )


@router.get("/eo/count-by-district", response_model=EOCountByDistrictResponse)
async def get_eo_count_by_district(
    db: Session = Depends(get_db),
):
    """
    Get EO counts grouped by district (sub-county).

    Returns the number of active EOs per district.

    Authentication: Bearer token required (STATISTIC_API_TOKEN)
    """
    service = StatisticService(db)
    data = service.get_eo_count_by_district()

    return EOCountByDistrictResponse(data=data)


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
