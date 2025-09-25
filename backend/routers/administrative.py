from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import AdministrativeLevel
from schemas.administrative import (
    AdministrativeDropdown,
    AdministrativeDropdownList,
    AdministrativeResponse,
)
from services.administrative_service import AdministrativeService

router = APIRouter(prefix="/administrative", tags=["administrative"])


@router.get("/levels", response_model=List[str])
def get_administrative_levels(
    db: Session = Depends(get_db),
):
    """Get all administrative levels (Public endpoint)"""
    try:
        levels = (
            db.query(AdministrativeLevel.name)
            .order_by(AdministrativeLevel.id)
            .all()
        )
        return [level[0] for level in levels]
    except Exception:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve administrative levels"
        )


@router.get("/", response_model=AdministrativeDropdownList)
def get_all_administrative(
    level: Optional[str] = Query(
        None, description="Filter by administrative level"
    ),
    parent_id: Optional[int] = Query(None, description="Filter by parent ID"),
    db: Session = Depends(get_db),
):
    """Get all administrative areas (requires level or parent_id parameter)"""
    if not level and parent_id is None:
        raise HTTPException(
            status_code=400,
            detail="Either 'level' or 'parent_id' parameter is required",
        )

    try:
        if level:
            administrative = AdministrativeService.get_administrative_by_level(
                db, level
            )
        elif parent_id is not None:
            administrative = (
                AdministrativeService.get_administrative_by_parent(
                    db, parent_id
                )
            )

        response_data = []
        for admin in administrative:
            response_data.append(
                AdministrativeDropdown(id=admin.id, name=admin.name)
            )

        return AdministrativeDropdownList(
            administrative=response_data, total=len(administrative)
        )
    except Exception:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve administrative data"
        )


@router.get("/{administrative_id}", response_model=AdministrativeResponse)
def get_administrative_by_id(
    administrative_id: int,
    db: Session = Depends(get_db),
):
    """Get administrative area by ID"""
    return AdministrativeService.get_administrative_by_id(
        db, administrative_id
    )
