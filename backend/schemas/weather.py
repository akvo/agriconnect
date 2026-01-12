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
