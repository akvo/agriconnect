from typing import List

from database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from schemas.customer import CropTypeInfo
from config import settings

router = APIRouter(prefix="/crop-types", tags=["crop-types"])


@router.get("/", response_model=List[CropTypeInfo])
async def get_crop_types(db: Session = Depends(get_db)):
    """Get all crop types from the database."""
    crop_types = settings.crop_types
    return [
        {
            "id": index + 1,
            "name": crop_type
        }
        for index, crop_type in enumerate(crop_types)
    ]
