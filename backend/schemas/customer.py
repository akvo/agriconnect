from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from models.customer import CustomerLanguage


class CustomerBase(BaseModel):
    phone_number: str
    full_name: Optional[str] = None
    language: CustomerLanguage = CustomerLanguage.EN


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    language: Optional[CustomerLanguage] = None


class CustomerResponse(CustomerBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True