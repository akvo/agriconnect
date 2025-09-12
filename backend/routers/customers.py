from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.customer_service import CustomerService
from schemas.customer import CustomerResponse, CustomerUpdate, CustomerCreate
from models.customer import Customer
from utils.auth_dependencies import admin_required
from typing import List

router = APIRouter(
    prefix="/customers",
    tags=["customers"]
)


@router.post("/", response_model=CustomerResponse)
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required)
):
    """Create a new customer (admin only)."""
    customer_service = CustomerService(db)
    
    # Check if customer already exists
    existing_customer = customer_service.get_customer_by_phone(customer_data.phone_number)
    if existing_customer:
        raise HTTPException(status_code=400, detail="Customer with this phone number already exists")
    
    customer = customer_service.create_customer(
        phone_number=customer_data.phone_number,
        language=customer_data.language
    )
    
    # Update additional fields if provided
    if customer_data.full_name:
        customer = customer_service.update_customer_profile(
            customer.id,
            full_name=customer_data.full_name
        )
    
    return customer


@router.get("/", response_model=List[CustomerResponse])
async def get_all_customers(
    db: Session = Depends(get_db),
    current_user=Depends(admin_required)
):
    """Get all customers (admin only)."""
    customers = db.query(Customer).all()
    return customers


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required)
):
    """Get specific customer by ID (admin only)."""
    customer_service = CustomerService(db)
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    customer_update: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required)
):
    """Update customer profile (admin only) - Progressive profiling."""
    customer_service = CustomerService(db)
    customer = customer_service.update_customer_profile(
        customer_id, 
        **customer_update.model_dump(exclude_unset=True)
    )
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return customer


@router.get("/phone/{phone_number}", response_model=CustomerResponse)
async def get_customer_by_phone(
    phone_number: str,
    db: Session = Depends(get_db),
    current_user=Depends(admin_required)
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
    current_user=Depends(admin_required)
):
    """Delete customer and all associated messages (admin only)."""
    customer_service = CustomerService(db)
    success = customer_service.delete_customer(customer_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return {"message": "Customer and associated messages deleted successfully"}