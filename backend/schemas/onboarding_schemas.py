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
    initial_question: str  # Question to ask user
    extraction_method: str  # Method name in OnboardingService
    matching_method: Optional[str]  # Ambiguity resolution method
    max_attempts: int  # Maximum collection attempts before skip
    field_type: str  # Data type: "string", "integer", "enum", "location"
    success_message_template: str  # Message after successful collection


# Onboarding fields registry - defines all profile fields to collect
ONBOARDING_FIELDS: List[OnboardingFieldConfig] = [
    # PRIORITY 1: Administration Location (REQUIRED)
    OnboardingFieldConfig(
        field_name="administration",
        db_field="customer_administrative",
        required=True,
        priority=1,
        initial_question=(
            "Welcome! To connect you with the right agricultural expert, "
            "I need to know your location.\n\n"
            "Please tell me: What ward or village are you from?"
        ),
        extraction_method="extract_location",
        matching_method="resolve_administration_ambiguity",
        max_attempts=3,
        field_type="location",
        success_message_template=(
            "Perfect! I've noted that you're in {value}."
        ),
    ),

    # PRIORITY 2: Crop Type (REQUIRED)
    OnboardingFieldConfig(
        field_name="crop_type",
        db_field="crop_type",
        required=True,
        priority=2,
        initial_question=(
            "What crops do you grow?\n\n"
            "For example: coffee, maize, avocado, etc."
        ),
        extraction_method="extract_crop_type",
        matching_method="resolve_crop_ambiguity",
        max_attempts=3,
        field_type="string",
        success_message_template=(
            "Great! I've noted that you grow {value}."
        ),
    ),

    # PRIORITY 3: Gender (OPTIONAL)
    OnboardingFieldConfig(
        field_name="gender",
        db_field="gender",
        required=False,
        priority=3,
        initial_question=(
            "To help us serve you better, may I know your gender?\n\n"
            "You can say: male, female, or other"
        ),
        extraction_method="extract_gender",
        matching_method=None,  # Direct enum mapping
        max_attempts=2,
        field_type="enum",
        success_message_template="Thank you for sharing.",
    ),

    # PRIORITY 4: Birth Year (OPTIONAL)
    OnboardingFieldConfig(
        field_name="birth_year",
        db_field="birth_year",
        required=False,
        priority=4,
        initial_question=(
            "What year were you born? "
            "You can also tell me your age if that's easier.\n\n"
            "For example: '1980' or 'I'm 45 years old'"
        ),
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
