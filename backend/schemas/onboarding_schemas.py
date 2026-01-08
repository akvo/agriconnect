"""
Onboarding service schemas for AI-driven farmer profile collection.

Supports generic multi-field onboarding (administration, crop, gender, age).
"""
from dataclasses import dataclass
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
    requires_weather_buttons: Optional[bool] = Field(
        None,
        description="for weather subscription buttons after this response",
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


class CropIdentificationResult(BaseModel):
    """Structured output for AI crop identification"""

    crop_name: Optional[str] = Field(
        None,
        description="The primary crop mentioned (normalized to standard name)",
    )
    confidence: str = Field(
        ..., description="Confidence level: 'high', 'medium', or 'low'"
    )
    possible_crops: List[str] = Field(
        default_factory=list,
        description="List of possible crop matches if ambiguous",
    )


# ============================================================================
# GENERIC ONBOARDING FIELD CONFIGURATIONS
# ============================================================================


@dataclass
class OnboardingFieldConfig:
    """Configuration for a single onboarding field"""

    field_name: str  # Unique identifier for the field
    db_field: str  # Column name in Customer model
    required: bool  # Whether field is required for completion
    priority: int  # Collection order (1 = first, 2 = second, etc.)
    extraction_method: str  # Method name in OnboardingService
    matching_method: Optional[str]  # Ambiguity resolution method
    max_attempts: int  # Maximum collection attempts before skip
    field_type: str  # Data type: "string", "integer", "enum", "location"
    success_message_template: str  # Message after successful collection
    # Save invalid value after max attempts


# Onboarding fields registry - defines all profile fields to collect
ONBOARDING_FIELDS: List[OnboardingFieldConfig] = [
    # PRIORITY 0: Language Preference (REQUIRED)
    OnboardingFieldConfig(
        field_name="language",
        db_field="language",
        required=True,
        priority=0,
        extraction_method="extract_language",
        matching_method=None,  # Direct enum mapping
        max_attempts=3,
        field_type="enum",
        success_message_template=(
            "Great! I'll communicate with you in {value}."
        ),
    ),
    # PRIORITY 1: Customer Name (REQUIRED)
    OnboardingFieldConfig(
        field_name="full_name",
        db_field="full_name",
        required=True,
        priority=1,
        extraction_method=None,
        matching_method=None,  # Direct text mapping
        max_attempts=1,
        field_type="string",
        success_message_template="Thank you, {value}!",
    ),
    # PRIORITY 2: Administration Location (REQUIRED)
    OnboardingFieldConfig(
        field_name="administration",
        db_field="customer_administrative",
        required=True,
        priority=2,
        extraction_method="extract_location",
        matching_method="resolve_administration_ambiguity",
        max_attempts=3,
        field_type="location",
        success_message_template=(
            "Perfect! I've noted that you're in {value}."
        ),
    ),
    # PRIORITY 3: Crop Type (REQUIRED)
    OnboardingFieldConfig(
        field_name="crop_type",
        db_field="crop_type",
        required=True,
        priority=3,
        extraction_method="extract_crop_type",
        matching_method="resolve_crop_ambiguity",
        max_attempts=3,
        field_type="string",
        success_message_template=("Great! I've noted that you grow {value}."),
    ),
    # PRIORITY 4: Gender (OPTIONAL)
    OnboardingFieldConfig(
        field_name="gender",
        db_field="gender",
        required=False,
        priority=4,
        extraction_method="extract_gender",
        matching_method=None,  # Direct enum mapping
        max_attempts=2,
        field_type="enum",
        success_message_template="Thank you for sharing.",
    ),
    # PRIORITY 5: Birth Year (OPTIONAL)
    OnboardingFieldConfig(
        field_name="birth_year",
        db_field="birth_year",
        required=False,
        priority=5,
        extraction_method="extract_birth_year",
        matching_method=None,  # AI converts age to birth year
        max_attempts=2,
        field_type="integer",
        success_message_template="Got it, thank you!",
    ),
]


def get_field_config(field_name: str) -> Optional[OnboardingFieldConfig]:
    """Get configuration for a specific field by name"""
    for config in ONBOARDING_FIELDS:
        if config.field_name == field_name:
            return config
    return None


def get_required_fields() -> List[OnboardingFieldConfig]:
    """Get all required fields"""
    return [f for f in ONBOARDING_FIELDS if f.required]


def get_optional_fields() -> List[OnboardingFieldConfig]:
    """Get all optional fields"""
    return [f for f in ONBOARDING_FIELDS if not f.required]


def get_fields_by_priority() -> List[OnboardingFieldConfig]:
    """Get all fields sorted by priority (ascending)"""
    return sorted(ONBOARDING_FIELDS, key=lambda x: x.priority)
