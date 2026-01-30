from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class TicketStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class TicketCustomer(BaseModel):
    id: Optional[int]
    name: Optional[str]
    phone_number: Optional[str]
    crop_type: Optional[str]
    gender: Optional[str]
    age: Optional[int]
    language: Optional[str]
    ward: Optional[str]


class TicketMessage(BaseModel):
    id: int
    body: str
    message_sid: str
    created_at: datetime


class TicketModel(BaseModel):
    id: Optional[int]
    ticket_number: Optional[str]
    customer: Optional[TicketCustomer]
    message: Optional[TicketMessage]
    context_message: Optional[TicketMessage] = None
    status: Optional[str]
    created_at: Optional[datetime]
    resolved_at: Optional[datetime]
    resolver: Optional[Any]
    tag: Optional[str] = None
    tag_confidence: Optional[float] = None


class TicketCreate(BaseModel):
    customer_id: int
    message_id: int


class TicketListResponse(BaseModel):
    tickets: List[TicketModel]
    total: int
    page: int
    size: int


class TicketResponse(BaseModel):
    ticket: TicketModel


class TicketMessagesResponse(BaseModel):
    messages: List[Any]
    total: int
    before_ts: Optional[str]
    limit: int
