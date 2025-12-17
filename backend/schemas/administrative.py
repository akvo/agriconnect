from typing import List, Optional

from pydantic import BaseModel, field_validator


class AdministrativeLevelBase(BaseModel):
    id: int
    name: str


class AdministrativeBase(BaseModel):
    code: str
    name: str
    level: AdministrativeLevelBase
    parent_id: Optional[int] = None
    path: str


class AdministrativeDropdown(BaseModel):
    """Lightweight schema for dropdown components"""

    id: int
    name: str


class AdministrativeResponse(AdministrativeBase):
    model_config = {"from_attributes": True}

    id: int


class AdministrativeCreate(BaseModel):
    code: str
    name: str
    level: str
    parent_id: Optional[int] = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, v):
        if not v or not v.strip():
            raise ValueError("Code is required")
        return v.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Name is required")
        return v.strip()

    @field_validator("level")
    @classmethod
    def validate_level(cls, v):
        if not v or not v.strip():
            raise ValueError("Level is required")
        valid_levels = ["country", "region", "district", "ward"]
        if v.lower() not in valid_levels:
            raise ValueError(
                f"Level must be one of: {', '.join(valid_levels)}"
            )
        return v.lower()


class AdministrativeUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip() if v else None


class AdministrativeAssign(BaseModel):
    administrative_ids: List[int]

    @field_validator("administrative_ids")
    @classmethod
    def validate_administrative_ids(cls, v):
        if not v:
            raise ValueError(
                "At least one administrative area must be selected"
            )
        if len(v) != len(set(v)):
            raise ValueError("Duplicate administrative areas are not allowed")
        return v


class AdministrativeDropdownList(BaseModel):
    """Lightweight list response for dropdown components"""

    administrative: List[AdministrativeDropdown]
    total: int
