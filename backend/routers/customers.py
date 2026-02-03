from typing import List, Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models.administrative import (
    UserAdministrative,
    CustomerAdministrative,
)
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

    For upper-level EOs (assigned to region/district), this returns
    all descendant ward IDs so they can access customers in subordinate areas.

    Args:
        user: The current authenticated user
        db: Database session

    Returns:
        Empty list for ADMIN (can access all), list of ward IDs for EO
    """
    from services.administrative_service import AdministrativeService

    if user.user_type == UserType.ADMIN:
        # Admin can access all customers
        return []

    # EO can access customers in their assigned areas and all descendant wards
    user_admins = (
        db.query(UserAdministrative)
        .filter(UserAdministrative.user_id == user.id)
        .all()
    )

    # Collect all accessible ward IDs (including descendants)
    all_ward_ids = set()
    for ua in user_admins:
        # Add the assigned area itself
        all_ward_ids.add(ua.administrative_id)
        # Add all descendant wards
        descendant_ids = AdministrativeService.get_descendant_ward_ids(
            db, ua.administrative_id
        )
        all_ward_ids.update(descendant_ids)

    return list(all_ward_ids)


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all customers"""
    # Load customers with administrative data
    customers = (
        db.query(Customer)
        .options(
            joinedload(Customer.customer_administrative).joinedload(
                CustomerAdministrative.administrative
            )
        )
    )
    if current_user.user_type != UserType.ADMIN:
        # filter by EO's assigned administrative areas
        user_admin_ids = _get_user_administrative_ids(current_user, db)
        customers = customers.join(
            Customer.customer_administrative
        ).filter(
            CustomerAdministrative.administrative_id.in_(user_admin_ids)
        )

    customers = customers.all()

    # Format response with administrative info
    customer_responses = []
    for customer in customers:
        admin_info = None
        if customer.customer_administrative:
            customer_admin = customer.customer_administrative[0]
            if customer_admin.administrative:
                admin = customer_admin.administrative
                admin_info = {
                    "id": admin.id,
                    "name": admin.name,
                    "parent_id": admin.parent_id,
                    "path": admin.path,
                    "level": {
                        "id": admin.level.id,
                        "name": admin.level.name,
                    } if admin.level else None,
                }
        customer_dict = {
            "id": customer.id,
            "phone_number": customer.phone_number,
            "full_name": customer.full_name,
            "language": customer.language,
            "crop_type": customer.crop_type,
            "gender": customer.gender,
            "age": customer.age,
            "administrative": admin_info,
            "created_at": customer.created_at,
            "updated_at": customer.updated_at,
        }
        customer_responses.append(customer_dict)
    return customer_responses


@router.get("/list", response_model=CustomerListResponse)
async def get_customers_list(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or phone"),
    administrative_ids: Optional[List[int]] = Query(
        None, description="Filter by ward IDs (admin only, multiple supported)"
    ),
    filters: Optional[List[str]] = Query(
        None,
        description=(
            "Profile filters in format 'field:value'. "
            "Multiple values supported. "
            "Examples: 'crop_type:Maize', 'gender:male', 'age_group:20-35'"
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated list of customers with optional filters.

    - **Admin users**: Can see all customers, can filter by specific ward(s)
    - **EO users**: Only see customers in their assigned ward(s)
    - Supports search by name/phone
    - Supports dynamic profile filtering (crop_type, gender, age_group, etc.)
    - Returns ward information for each customer

    **Filter Examples**:
    - Single filter: `?filters=crop_type:Maize`
    - Multiple values (OR):
      `?filters=crop_type:Maize&filters=crop_type:Avocado`
    - Multiple fields (AND): `?filters=crop_type:Maize&filters=gender:male`
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

    # Parse filters into dict with lists
    profile_filters = None
    if filters:
        profile_filters = defaultdict(list)
        for filter_str in filters:
            if ":" not in filter_str:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid filter format: '{filter_str}'. "
                        "Use 'field:value'"
                    ),
                )
            field, value = filter_str.split(":", 1)
            profile_filters[field.strip()].append(value.strip())
        profile_filters = dict(profile_filters)  # Convert to regular dict

    # Get customers list
    customers, total = customer_service.get_customers_list(
        page=page,
        size=size,
        search=search,
        administrative_ids=filter_administrative_ids,
        profile_filters=profile_filters,
    )

    return CustomerListResponse(
        customers=customers, total=total, page=page, size=size
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
