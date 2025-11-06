"""
Onboarding service schemas for AI-driven farmer location collection.

Stage 1: Administrative location data (province, district, ward)
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class LocationData(BaseModel):
    """Extracted location data from farmer's message"""

    province: Optional[str] = Field(
        None, description="Province/region/county name mentioned"
    )
    district: Optional[str] = Field(
        None, description="District/sub-county name mentioned"
    )
    ward: Optional[str] = Field(
        None, description="Ward/location name mentioned"
    )
    full_text: Optional[str] = Field(
        None, description="Full location description from farmer"
    )


class MatchCandidate(BaseModel):
    """A single matched administrative area candidate"""

    id: int = Field(..., description="Administrative area ID")
    name: str = Field(..., description="Administrative area name")
    path: str = Field(..., description="Full hierarchical path")
    level: str = Field(..., description="Level name (ward, district, etc)")
    score: float = Field(..., description="Match score (0-100)")


class OnboardingResponse(BaseModel):
    """Response from onboarding service"""

    message: str = Field(..., description="Message to send to farmer")
    status: str = Field(
        ...,
        description=(
            "Onboarding status: in_progress, completed, "
            "failed, awaiting_selection"
        ),
    )
    matched_ward_id: Optional[int] = Field(
        None, description="Ward ID if single match found (automatic matching)"
    )
    selected_ward_id: Optional[int] = Field(
        None, description="Ward ID if selected by farmer (manual selection)"
    )
    candidates: Optional[List[MatchCandidate]] = Field(
        None, description="List of candidate wards for farmer to choose from"
    )
    attempts: int = Field(
        ..., description="Current number of onboarding attempts"
    )
    extracted_location: Optional[LocationData] = Field(
        None, description="Location data extracted from message"
    )


class SelectionRequest(BaseModel):
    """Request to select from ambiguous candidates"""

    customer_phone: str = Field(..., description="Customer phone number")
    selection: str = Field(
        ..., description="Farmer's selection (e.g., '1', 'first')"
    )


class SelectionResponse(BaseModel):
    """Response after processing selection"""

    message: str = Field(..., description="Confirmation message")
    status: str = Field(..., description="Onboarding status after selection")
    selected_ward_id: Optional[int] = Field(
        None, description="Selected ward ID"
    )
