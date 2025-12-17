from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from models.customer import AgeGroup, CustomerLanguage, Gender


class CustomerBase(BaseModel):
    phone_number: str
    full_name: Optional[str] = None
    language: CustomerLanguage = CustomerLanguage.EN
    crop_type_id: Optional[int] = None
    gender: Optional[Gender] = None
    birth_year: Optional[int] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    language: Optional[CustomerLanguage] = None
    crop_type: Optional[str] = None
    gender: Optional[Gender] = None
    age: Optional[int] = None
    ward_id: Optional[int] = None


class CustomerResponse(CustomerBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CustomerAdministrativeInfo(BaseModel):
    """Administrative area information for a customer."""

    id: Optional[int] = None
    name: Optional[str] = None
    path: Optional[str] = None


class CropTypeInfo(BaseModel):
    """Crop type information."""

    id: int
    name: str

    class Config:
        from_attributes = True


class CustomerListItem(BaseModel):
    """Customer item in the list response with ward information."""

    id: int
    full_name: Optional[str] = None
    phone_number: str
    language: CustomerLanguage
    gender: Optional[Gender] = None
    age_group: Optional[AgeGroup] = None
    birth_year: Optional[int] = None
    crop_type: Optional[str] = None
    administrative: CustomerAdministrativeInfo

    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """Paginated response for customer list."""

    customers: List[CustomerListItem]
    total: int
    page: int
    size: int
