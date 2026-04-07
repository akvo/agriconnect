"""
Schemas for Statistics API responses.

Provides Pydantic models for farmer and EO statistics endpoints.
"""

from typing import List, Optional

from pydantic import BaseModel


# Filter schemas
class FarmerStatsFilters(BaseModel):
    """Applied filters for farmer statistics."""

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    administrative_id: Optional[int] = None
    phone_prefix: Optional[str] = None
    crop_type: Optional[str] = None
    active_days: int = 30


class EOStatsFilters(BaseModel):
    """Applied filters for EO statistics."""

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    eo_id: Optional[int] = None
    administrative_id: Optional[int] = None


class RegistrationFilters(BaseModel):
    """Applied filters for registration data."""

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    administrative_id: Optional[int] = None
    phone_prefix: Optional[str] = None
    crop_type: Optional[str] = None
    group_by: str = "day"


# Farmer statistics schemas
class OnboardingStats(BaseModel):
    """Onboarding statistics."""

    started: int
    completed: int
    completion_rate: float


class ActivityStats(BaseModel):
    """Farmer activity statistics."""

    active_farmers: int
    dormant_farmers: int
    active_rate: float
    total_questions: int = 0
    avg_days_to_first_question: Optional[float] = None
    avg_questions_per_farmer: Optional[float] = None


class FeatureStats(BaseModel):
    """Feature usage statistics."""

    weather_subscribers: int


class EscalationStats(BaseModel):
    """Escalation statistics."""

    total_escalated: int
    farmers_who_escalated: int


class FarmerStatsResponse(BaseModel):
    """Complete farmer statistics response."""

    onboarding: OnboardingStats
    activity: ActivityStats
    features: FeatureStats
    escalations: EscalationStats
    filters: FarmerStatsFilters


# Farmer stats by ward schemas
class WardFarmerStats(BaseModel):
    """Farmer statistics for a single ward."""

    ward_id: int
    ward_name: str
    ward_path: str
    registered_farmers: int
    incomplete_registration: int
    farmers_with_questions: int
    total_questions: int
    farmers_who_escalated: int
    total_escalations: int


class FarmerStatsByWardResponse(BaseModel):
    """Farmer statistics grouped by ward."""

    data: List[WardFarmerStats]
    filters: FarmerStatsFilters


# Registration chart schemas
class RegistrationDataPoint(BaseModel):
    """Single data point for registration chart."""

    date: str
    count: int


class RegistrationChartResponse(BaseModel):
    """Registration chart data response."""

    data: List[RegistrationDataPoint]
    total: int
    filters: RegistrationFilters


# EO statistics schemas
class EOTicketStats(BaseModel):
    """Ticket statistics for EOs."""

    open: int
    closed: int
    avg_response_time_hours: Optional[float] = None


class EOMessageStats(BaseModel):
    """Message statistics for EOs."""

    bulk_messages_sent: int


class EOStatsResponse(BaseModel):
    """Complete EO statistics response."""

    tickets: EOTicketStats
    messages: EOMessageStats
    filters: EOStatsFilters


# EO stats by EO schemas
class EOIndividualStats(BaseModel):
    """Statistics for a single EO."""

    eo_id: int
    eo_name: str
    district: Optional[str] = None
    total_replies: int
    tickets_closed: int


class EOStatsByEOResponse(BaseModel):
    """EO statistics grouped by individual EO."""

    data: List[EOIndividualStats]
    filters: EOStatsFilters


# EO count schema
class EOCountResponse(BaseModel):
    """EO count response."""

    count: int
    administrative_id: Optional[int] = None


# EO list schemas
class EOListItem(BaseModel):
    """Single EO item for dropdown."""

    id: int
    name: str


class EOListResponse(BaseModel):
    """List of EOs for filter dropdown."""

    data: List[EOListItem]


# Aggregate endpoint schemas
class AggregateFilters(BaseModel):
    """Applied filters for aggregate endpoints."""

    level: str  # "region", "district", or "ward"
    administrative_id: Optional[int] = None
    crop_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AvailableAdminItem(BaseModel):
    """Single administrative item in available filters."""

    id: int
    name: str


class AvailableFilters(BaseModel):
    """Available filter options that have data."""

    regions: List[AvailableAdminItem]
    districts: List[AvailableAdminItem]
    wards: List[AvailableAdminItem]
    crop_types: List[str]


class FarmerAggregateItem(BaseModel):
    """Farmer statistics for a single administrative area."""

    id: int
    name: str
    path: str
    farmer_count: int
    completed_onboarding: int
    incomplete_onboarding: int
    questions_count: int
    escalations_count: int
    weather_subscribers: int


class FarmerAggregateResponse(BaseModel):
    """Farmer data aggregated by administrative level."""

    data: List[FarmerAggregateItem]
    filters: AggregateFilters
    available: AvailableFilters


class EOAggregateItem(BaseModel):
    """EO statistics for a single administrative area."""

    id: int
    name: str
    path: str
    eo_count: int
    open_tickets: int
    closed_tickets: int
    total_replies: int


class EOAggregateResponse(BaseModel):
    """EO data aggregated by administrative level."""

    data: List[EOAggregateItem]
    filters: AggregateFilters
    available: AvailableFilters
