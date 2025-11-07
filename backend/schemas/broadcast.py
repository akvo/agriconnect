"""
Schemas for broadcast group and message management.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator

from models.customer import AgeGroup


# ========== Broadcast Group Schemas ==========

class BroadcastGroupCreate(BaseModel):
    """Request schema for creating a broadcast group with filters"""
    name: str = Field(..., min_length=1, max_length=255)
    crop_types: Optional[List[int]] = Field(
        None, description="Filter by crop type IDs"
    )
    age_groups: Optional[List[str]] = Field(
        None, description="Filter by age groups: ['20-35', '36-50', '51+']"
    )
    customer_ids: List[int] = Field(
        ..., min_items=1, max_items=500,
        description="Selected customer IDs after filtering"
    )

    @validator('age_groups')
    def validate_age_groups(cls, v):
        if v:
            valid_groups = [age.value for age in AgeGroup]
            for group in v:
                if group not in valid_groups:
                    raise ValueError(
                        f"Invalid age group: {group}. "
                        f"Must be one of {valid_groups}"
                    )
        return v

    @validator('customer_ids')
    def validate_customer_ids(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Duplicate customer IDs not allowed')
        return v


class BroadcastGroupUpdate(BaseModel):
    """Request schema for updating a broadcast group"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    crop_types: Optional[List[int]] = Field(
        None, description="Filter by crop type IDs"
    )
    age_groups: Optional[List[str]] = Field(
        None, description="Filter by age groups"
    )
    customer_ids: Optional[List[int]] = Field(
        None, min_items=1, max_items=500,
        description="Selected customer IDs after filtering"
    )

    @validator('age_groups')
    def validate_age_groups(cls, v):
        if v:
            valid_groups = [age.value for age in AgeGroup]
            for group in v:
                if group not in valid_groups:
                    raise ValueError(
                        f"Invalid age group: {group}. "
                        f"Must be one of {valid_groups}"
                    )
        return v

    @validator('customer_ids')
    def validate_customer_ids(cls, v):
        if v and len(v) != len(set(v)):
            raise ValueError('Duplicate customer IDs not allowed')
        return v


class BroadcastGroupContact(BaseModel):
    """Schema for broadcast group contact info"""
    customer_id: int
    phone_number: str
    full_name: Optional[str] = None

    class Config:
        from_attributes = True


class BroadcastGroupResponse(BaseModel):
    """Response schema for broadcast group"""
    id: int
    name: str
    crop_types: Optional[List[int]] = None
    age_groups: Optional[List[str]]
    administrative_id: Optional[int]
    created_by: int
    contact_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BroadcastGroupDetail(BaseModel):
    """Detailed broadcast group response with contacts"""
    id: int
    name: str
    crop_types: Optional[List[int]] = None
    age_groups: Optional[List[str]]
    administrative_id: Optional[int]
    created_by: int
    contacts: List[BroadcastGroupContact]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== Broadcast Message Schemas ==========

class BroadcastMessageCreate(BaseModel):
    """Request schema for creating a broadcast"""
    message: str = Field(..., min_length=1, max_length=1600)
    group_ids: List[int] = Field(..., min_items=1, max_items=10)

    @validator('group_ids')
    def validate_group_ids(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Duplicate group IDs not allowed')
        return v


class BroadcastRecipientStatus(BaseModel):
    """Schema for individual recipient status"""
    customer_id: int
    phone_number: str
    full_name: Optional[str]
    status: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class BroadcastMessageResponse(BaseModel):
    """Response schema for broadcast creation"""
    id: int
    message: str
    status: str
    total_recipients: int
    queued_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class BroadcastMessageStatus(BaseModel):
    """Detailed status of a broadcast"""
    id: int
    message: str
    status: str
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    recipients: List[BroadcastRecipientStatus]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
