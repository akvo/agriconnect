from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from models.device import DevicePlatform


class DeviceRegisterRequest(BaseModel):
    """Request schema for registering a device for push notifications."""

    push_token: str = Field(
        ...,
        description="Expo push token for the device (ExponentPushToken[...])",
        min_length=1,
    )
    platform: DevicePlatform = Field(
        ...,
        description="Device platform (ios or android)",
    )
    app_version: Optional[str] = Field(
        None,
        description="App version (e.g., '1.0.0')",
        max_length=50,
    )


class DeviceResponse(BaseModel):
    """Response schema for device operations."""

    id: int
    user_id: int
    push_token: str
    platform: str
    app_version: Optional[str]
    is_active: bool
    last_seen_at: datetime
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DeviceUpdateRequest(BaseModel):
    """Request schema for updating device status."""

    is_active: Optional[bool] = Field(
        None,
        description=(
            "Set to false to disable push notifications for this device"
        ),
    )
