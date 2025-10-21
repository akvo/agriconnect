from typing import List

from database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from models.customer import CropType
from schemas.customer import CropTypeInfo

router = APIRouter(prefix="/crop-types", tags=["crop-types"])


@router.get("/", response_model=List[CropTypeInfo])
async def get_crop_types(db: Session = Depends(get_db)):
    """Get all crop types from the database."""
    crop_types = db.query(CropType).all()
    return [CropTypeInfo.from_orm(ct) for ct in crop_types]
