"""
Weather Broadcast Schemas
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LanguageEnum(str, Enum):
    """Supported languages for weather broadcasts"""

    ENGLISH = "en"
    SWAHILI = "sw"


class WeatherMessageRequest(BaseModel):
    """Request schema for weather message generation"""

    location: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Location name (e.g., 'Nairobi', 'Dar es Salaam')",
        json_schema_extra={"example": "Nairobi"},
    )
    lat: Optional[float] = Field(
        default=None,
        ge=-90,
        le=90,
        description="Latitude for OneCall 3.0 API (optional)",
        json_schema_extra={"example": -1.2921},
    )
    lon: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180,
        description="Longitude for OneCall 3.0 API (optional)",
        json_schema_extra={"example": 36.8219},
    )
    crop_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Crop type for specific weather suggestions",
        json_schema_extra={"example": "Avocado"},
    )
    language: LanguageEnum = Field(
        default=LanguageEnum.ENGLISH,
        description="Language for the generated message",
    )


class WeatherBroadcastTriggerResponse(BaseModel):
    """Response schema for manual weather broadcast trigger"""

    status: str = Field(
        ...,
        description="Status of the trigger request",
        json_schema_extra={"example": "queued"},
    )
    task_id: str = Field(
        ...,
        description="Celery task ID for tracking",
        json_schema_extra={"example": "abc123-def456"},
    )
    message: Optional[str] = Field(
        default=None,
        description="Additional message",
    )
