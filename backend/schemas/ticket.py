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


class TicketMessage(BaseModel):
    id: Optional[int]
    body: Optional[str]


class TicketModel(BaseModel):
    id: Optional[int]
    ticket_number: Optional[str]
    customer: Optional[TicketCustomer]
    message: Optional[TicketMessage]
    status: Optional[str]
    created_at: Optional[datetime]
    resolved_at: Optional[datetime]
    resolver: Optional[Any]


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
