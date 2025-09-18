from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.service_token import ServiceToken
from models.user import User
from services.service_token_service import ServiceTokenService
from utils.auth_dependencies import admin_required

router = APIRouter(prefix="/admin/service-tokens", tags=["service-tokens"])


class ServiceTokenCreate(BaseModel):
    service_name: str
    scopes: str = None


class ServiceTokenResponse(BaseModel):
    id: int
    service_name: str
    scopes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ServiceTokenCreateResponse(BaseModel):
    token: ServiceTokenResponse
    plain_token: str
    message: str


@router.post("/", response_model=ServiceTokenCreateResponse)
def create_service_token(
    token_data: ServiceTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Create a new service token (Admin only)"""
    # Check if service token already exists for this service
    existing_token = ServiceTokenService.get_token_by_service_name(
        db, token_data.service_name
    )
    if existing_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Service token already exists for "
                    f"'{token_data.service_name}'")
        )

    service_token, plain_token = ServiceTokenService.create_token(
        db, token_data.service_name, token_data.scopes
    )

    message = ("Service token created successfully. Store the plain token "
               "securely - it won't be shown again.")

    return ServiceTokenCreateResponse(
        token=ServiceTokenResponse.model_validate(service_token),
        plain_token=plain_token,
        message=message
    )


@router.get("/", response_model=List[ServiceTokenResponse])
def list_service_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """List all service tokens (Admin only)"""
    tokens = db.query(ServiceToken).all()
    return [ServiceTokenResponse.model_validate(token) for token in tokens]


@router.delete("/{token_id}")
def delete_service_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    """Delete a service token (Admin only)"""
    success = ServiceTokenService.delete_token(db, token_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service token not found"
        )

    return {"message": "Service token deleted successfully"}
