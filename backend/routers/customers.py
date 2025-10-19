from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.administrative import UserAdministrative
from models.customer import Customer
from models.user import User, UserType
from schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
)
from services.customer_service import CustomerService
from utils.auth_dependencies import admin_required, get_current_user

router = APIRouter(prefix="/customers", tags=["customers"])


def _get_user_administrative_ids(user: User, db: Session) -> List[int]:
    """Get list of administrative IDs accessible by the user.

    Args:
        user: The current authenticated user
        db: Database session

    Returns:
        Empty list for ADMIN (can access all), list of ward IDs for EO
    """
    if user.user_type == UserType.ADMIN:
        # Admin can access all customers
        return []

    # EO can only access customers in their assigned administrative areas
    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )

    return [ua.administrative_id for ua in user_admins]


@router.post("/", response_model=CustomerResponse)
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required),
):
    """Create a new customer (admin only)."""
    customer_service = CustomerService(db)

    # Check if customer already exists
    existing_customer = customer_service.get_customer_by_phone(
        customer_data.phone_number
    )
    if existing_customer:
        raise HTTPException(
            status_code=400,
            detail="Customer with this phone number already exists",
        )

    customer = customer_service.create_customer(
        phone_number=customer_data.phone_number,
        language=customer_data.language,
    )

    # Update additional fields if provided
    if customer_data.full_name:
        customer = customer_service.update_customer_profile(
            customer.id, full_name=customer_data.full_name
        )

    return customer


@router.get("/", response_model=List[CustomerResponse])
async def get_all_customers(
    db: Session = Depends(get_db), current_user=Depends(admin_required)
):
    """Get all customers (admin only) - Legacy endpoint."""
    customers = db.query(Customer).all()
    return customers


@router.get("/list", response_model=CustomerListResponse)
async def get_customers_list(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or phone"),
    administrative_ids: Optional[List[int]] = Query(
        None, description="Filter by ward IDs (admin only, multiple supported)"
    ),
    crop_types: Optional[List[str]] = Query(
        None, description="Filter by crop types"
    ),
    age_groups: Optional[List[str]] = Query(
        None, description="Filter by age groups"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated list of customers with optional filters.

    - **Admin users**: Can see all customers, can filter by specific ward(s)
    - **EO users**: Only see customers in their assigned ward(s)
    - Supports search by name/phone
    - Supports filtering by crop types and age groups
    - Returns ward information for each customer
    """
    customer_service = CustomerService(db)

    # Get administrative IDs based on user role
    user_administrative_ids = _get_user_administrative_ids(current_user, db)

    # Determine which administrative IDs to filter by
    if current_user.user_type == UserType.ADMIN:
        # Admin can optionally filter by specific ward(s)
        if administrative_ids:
            filter_administrative_ids = administrative_ids
        else:
            # No filter - show all customers
            filter_administrative_ids = None
    else:
        # EO users - always filter by their assigned wards
        if not user_administrative_ids:
            # EO has no ward assignments, return empty list
            return CustomerListResponse(
                customers=[], total=0, page=page, size=size
            )
        filter_administrative_ids = user_administrative_ids

    # Get customers list
    customers, total = customer_service.get_customers_list(
        page=page,
        size=size,
        search=search,
        administrative_ids=filter_administrative_ids,
        crop_types=crop_types,
        age_groups=age_groups,
    )

    return CustomerListResponse(
        customers=customers, total=total, page=page, size=size
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required),
):
    """Get specific customer by ID (admin only)."""
    CustomerService(db)
    customer = db.query(Customer).filter(Customer.id == customer_id).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    customer_update: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required),
):
    """Update customer profile (admin only) - Progressive profiling."""
    customer_service = CustomerService(db)
    customer = customer_service.update_customer_profile(
        customer_id, **customer_update.model_dump(exclude_unset=True)
    )

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


@router.get("/phone/{phone_number}", response_model=CustomerResponse)
async def get_customer_by_phone(
    phone_number: str,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required),
):
    """Get customer by phone number (admin only)."""
    customer_service = CustomerService(db)
    customer = customer_service.get_customer_by_phone(phone_number)

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required),
):
    """Delete customer and all associated messages (admin only)."""
    customer_service = CustomerService(db)
    success = customer_service.delete_customer(customer_id)

    if not success:
        raise HTTPException(status_code=404, detail="Customer not found")

    return {"message": "Customer and associated messages deleted successfully"}
