# Generic Onboarding System - Implementation Plan

## Executive Summary

This document outlines the refactoring of AgriConnect's onboarding system from a **single-purpose administration collector** to a **generic, configuration-driven profile collection system** that can handle multiple farmer profile fields (administration/ward, crop type, gender, age group, etc.) in a scalable, maintainable way.

## Problem Statement

### Current State

The existing onboarding system only collects **administration/ward** information:

```python
# backend/models/customer.py - CURRENT
class Customer(Base):
    onboarding_status = Column(Enum(OnboardingStatus))  # For administration only
    onboarding_attempts = Column(Integer)
    onboarding_candidates = Column(Text)  # JSON array of ward IDs
```

**File**: `backend/services/onboarding_service.py`
- Hard-coded to handle ward/location extraction
- OpenAI extracts province/district/ward
- Fuzzy matches against `administrative` table
- Saves to `CustomerAdministrative` table

### New Requirements

We need to collect additional profile fields:
1. **Administration/Ward** (existing) - Priority 1
2. **Crop Type** - Priority 2
3. **Gender** (optional) - Priority 3
4. **Age Group** (optional) - Priority 4
5. **Future fields** - Farm size, years of experience, etc.

### Naive Approach (Why It Fails)

Creating separate status fields for each profile attribute:

```python
# BAD APPROACH - NOT SCALABLE ❌
class Customer(Base):
    onboarding_status = Column(...)           # For administration
    crop_collection_status = Column(...)      # For crop
    gender_collection_status = Column(...)    # For gender
    age_collection_status = Column(...)       # For age
    # ... more status fields for each new attribute
```

**Problems:**
- ❌ Schema bloat (new column per field)
- ❌ Duplicate services (one per field)
- ❌ Complex state management
- ❌ No clear priority order
- ❌ Maintenance nightmare
- ❌ Database migrations for every new field

---

## Solution: Generic Onboarding System

### Design Principles

1. **Single State Machine** - One `onboarding_status` for all fields
2. **Configuration-Driven** - Fields defined in config, not code
3. **Priority-Based** - Fields collected in defined order
4. **Extensible** - Add new fields without schema changes
5. **Field-Agnostic** - Service handles any field type generically
6. **Backward Compatible** - Existing administration flow unchanged

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│              ONBOARDING CONFIGURATION                       │
│  (Defines all profile fields, priority, extraction logic)  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│            GENERIC ONBOARDING SERVICE                       │
│  - get_next_incomplete_field()                              │
│  - process_onboarding_message() → handles ANY field         │
│  - Field-specific extractors (extract_location, etc.)       │
│  - Field-specific matchers (match_crop, etc.)               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              CUSTOMER MODEL (SIMPLIFIED)                    │
│  - onboarding_status (overall progress)                     │
│  - current_onboarding_field (which field collecting now)    │
│  - onboarding_candidates (JSON - any field's options)       │
│  - onboarding_attempts (JSON - attempts per field)          │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema Changes

### Current Schema

```python
# backend/models/customer.py - BEFORE
class Customer(Base):
    # Administration onboarding (current)
    onboarding_status = Column(
        Enum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED
    )  # NOT_STARTED, IN_PROGRESS, COMPLETED, FAILED

    onboarding_attempts = Column(Integer, default=0)
    onboarding_candidates = Column(Text, nullable=True)  # JSON array of ward IDs

    # Profile fields
    crop_type = Column(String, nullable=True)  # Crop type name (validated against config)
    gender = Column(Enum(Gender), nullable=True)
    birth_year = Column(Integer, nullable=True)  # Birth year (e.g., 1980) - never becomes stale
```

### New Schema (Generic)

```python
# backend/models/customer.py - AFTER
class Customer(Base):
    # GENERIC ONBOARDING SYSTEM
    onboarding_status = Column(
        Enum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED,
        nullable=False
    )  # Overall onboarding progress (all fields)

    current_onboarding_field = Column(String, nullable=True)
    # Current field being collected: "administration", "crop_type", "gender", etc.
    # NULL = not started or completed

    onboarding_candidates = Column(JSON, nullable=True)
    # Ambiguous matches for ANY field (JSON object, not array)
    # Example: {"crop_type": ["Cacao", "Avocado"], "administration": [45, 46]}
    # Key = field_name, Value = array of candidate values (strings for crop_type, IDs for administration)

    onboarding_attempts = Column(JSON, nullable=True)
    # Attempt counter per field (JSON object)
    # Example: {"administration": 2, "crop_type": 1, "gender": 0}
    # Key = field_name, Value = attempt count

    # Profile fields (no foreign key relationship for crop_type)
    crop_type = Column(String, nullable=True)  # Crop type name (validated against config)
    gender = Column(Enum(Gender), nullable=True)
    birth_year = Column(Integer, nullable=True)  # Birth year (e.g., 1980) - never becomes stale
    
    # Calculated properties (not stored in database)
    @property
    def age(self) -> Optional[int]:
        """Calculate current age from birth year"""
        if not self.birth_year:
            return None
        from datetime import datetime
        return datetime.now().year - self.birth_year
    
    @property
    def age_group(self) -> Optional[str]:
        """Calculate current age group from age"""
        age = self.age
        if not age:
            return None
        if age <= 35:
            return "20-35"
        elif age <= 50:
            return "36-50"
        else:
            return "51+"
```

### OnboardingStatus Enum (Unchanged)

```python
class OnboardingStatus(enum.Enum):
    NOT_STARTED = "not_started"   # No fields collected yet
    IN_PROGRESS = "in_progress"   # Currently collecting fields
    COMPLETED = "completed"       # All required fields collected
    FAILED = "failed"             # Max attempts exceeded (deprecated in new system)
```

### New Enums for Profile Fields

```python
# backend/models/customer.py

class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

# Note: AgeGroup is NOT stored as enum - it's calculated dynamically from birth_year
# Age groups: "20-35", "36-50", "51+" (calculated via @property age_group)
```

### Migration Strategy

#### Current State Analysis

Based on existing migrations:
- **Migration `0f2e1f09e80b`** (2025-10-21): Created `crop_types` table with FK relationship
- **Migration `1374b11aa9f3`** (2025-11-06): Added onboarding fields (`onboarding_status`, `onboarding_attempts`, `onboarding_candidates`)

**Current Schema:**
```python
# backend/models/customer.py - CURRENT STATE
class Customer(Base):
    crop_type_id = Column(Integer, ForeignKey("crop_types.id"), nullable=True)  # FK to crop_types table
    age_group = Column(Enum(AgeGroup), nullable=True)  # Already exists (will be removed)
    
    # Onboarding fields (from migration 1374b11aa9f3)
    onboarding_status = Column(Enum(OnboardingStatus), default=OnboardingStatus.NOT_STARTED)
    onboarding_attempts = Column(Integer, default=0)  # Integer, not JSON
    onboarding_candidates = Column(Text, nullable=True)  # Text, not JSON
```

#### New Migration Required

**File**: `backend/alembic/versions/YYYYMMDD_HHMMSS_generic_onboarding_system.py`

```python
"""generic onboarding system - refactor to config-driven approach

Revision ID: XXXXXX
Revises: a1b2c3d4e5f6  # Latest migration (add_media_tracking or newer)
Create Date: YYYY-MM-DD HH:MM:SS

Changes:
1. Remove crop_types table dependency - migrate to string field with JSON config
2. Add Gender enum and column
3. Add current_onboarding_field tracking column
4. Convert onboarding_attempts from Integer to JSON (per-field tracking)
5. Convert onboarding_candidates from Text to JSON (multi-field support)
6. Replace age_group enum with birth_year integer (age calculated dynamically)
"""
from alembic import op
import sqlalchemy as sa
import json

revision = 'XXXXXX'
down_revision = 'a1b2c3d4e5f6'  # Update to your latest migration
branch_labels = None
depends_on = None


def upgrade():
    """
    Refactor onboarding system to be generic and configuration-driven
    """
    
    # ================================================================
    # 1. CREATE GENDER ENUM
    # ================================================================
    gender_enum = sa.Enum(
        'male', 'female', 'other',
        name='gender'
    )
    gender_enum.create(op.get_bind(), checkfirst=True)

    # ================================================================
    # 2. ADD current_onboarding_field COLUMN
    # ================================================================
    # Tracks which field is currently being collected
    op.add_column(
        'customers',
        sa.Column('current_onboarding_field', sa.String(), nullable=True)
    )

    # ================================================================
    # 3. CONVERT onboarding_candidates: Text → JSON
    # ================================================================
    # Old: Text field storing JSON array of ward IDs: "[45, 46, 47]"
    # New: JSON object with field names as keys: {"administration": [45, 46], "crop_type": ["Cacao", "Avocado"]}
    
    # Step 3a: Add temporary JSON column
    op.add_column(
        'customers',
        sa.Column('onboarding_candidates_json', sa.JSON(), nullable=True)
    )

    # Step 3b: Migrate existing data
    # Convert "[1,2,3]" → {"administration": [1,2,3]}
    op.execute("""
        UPDATE customers
        SET onboarding_candidates_json = 
            CASE
                WHEN onboarding_candidates IS NOT NULL 
                    AND onboarding_candidates != '' 
                    AND onboarding_candidates != 'null'
                    AND onboarding_candidates::text ~ '^\\[.*\\]$'  -- Valid JSON array
                THEN json_build_object('administration', onboarding_candidates::json)
                ELSE NULL
            END
        WHERE onboarding_candidates IS NOT NULL
    """)

    # Step 3c: Drop old column and rename new one
    op.drop_column('customers', 'onboarding_candidates')
    op.alter_column(
        'customers',
        'onboarding_candidates_json',
        new_column_name='onboarding_candidates',
        type_=sa.JSON()
    )

    # ================================================================
    # 4. CONVERT onboarding_attempts: Integer → JSON
    # ================================================================
    # Old: Single integer for all fields
    # New: JSON object tracking attempts per field: {"administration": 2, "crop_type": 1}
    
    # Step 4a: Add temporary JSON column
    op.add_column(
        'customers',
        sa.Column('onboarding_attempts_json', sa.JSON(), nullable=True)
    )

    # Step 4b: Migrate existing data
    # Convert integer 2 → {"administration": 2}
    op.execute("""
        UPDATE customers
        SET onboarding_attempts_json = 
            CASE
                WHEN onboarding_attempts > 0
                THEN json_build_object('administration', onboarding_attempts)
                ELSE '{}'::json
            END
    """)

    # Step 4c: Drop old column and rename new one
    op.drop_column('customers', 'onboarding_attempts')
    op.alter_column(
        'customers',
        'onboarding_attempts_json',
        new_column_name='onboarding_attempts',
        type_=sa.JSON()
    )

    # ================================================================
    # 5. MIGRATE CROP_TYPE: FK → String
    # ================================================================
    # Remove crop_types table dependency, use string field validated against JSON config
    
    # Step 5a: Add new crop_type string column
    op.add_column(
        'customers',
        sa.Column('crop_type_new', sa.String(), nullable=True)
    )

    # Step 5b: Migrate existing data - copy crop names from crop_types table
    op.execute("""
        UPDATE customers c
        SET crop_type_new = ct.name
        FROM crop_types ct
        WHERE c.crop_type_id = ct.id
    """)

    # Step 5c: Drop foreign key constraint
    op.drop_constraint(
        'fk_customers_crop_type_id',
        'customers',
        type_='foreignkey'
    )

    # Step 5d: Drop old crop_type_id column
    op.drop_column('customers', 'crop_type_id')

    # Step 5e: Rename new column
    op.alter_column(
        'customers',
        'crop_type_new',
        new_column_name='crop_type'
    )

    # Step 5f: Drop crop_types table
    # The /crop-types endpoint will be updated to read from config.json instead
    # Mobile app compatibility maintained by using array index as ID
    op.drop_index('ix_crop_types_id', table_name='crop_types')
    op.drop_table('crop_types')

    # ================================================================
    # 6. ADD GENDER COLUMN
    # ================================================================
    op.add_column(
        'customers',
        sa.Column(
            'gender',
            sa.Enum('male', 'female', 'other', name='gender'),
            nullable=True
        )
    )

    # ================================================================
    # 7. REPLACE age_group WITH birth_year
    # ================================================================
    # Step 7a: Add birth_year column
    op.add_column(
        'customers',
        sa.Column('birth_year', sa.Integer(), nullable=True)
    )
    
    # Step 7b: Migrate existing age_group data to approximate birth_year
    # This is a best-effort migration since age_group only gives ranges
    current_year = 2025
    op.execute(f"""
        UPDATE customers
        SET birth_year = CASE
            WHEN age_group = '20-35' THEN {current_year} - 27  -- Midpoint of range
            WHEN age_group = '36-50' THEN {current_year} - 43  -- Midpoint of range
            WHEN age_group = '51+' THEN {current_year} - 60    -- Approximate for seniors
            ELSE NULL
        END
        WHERE age_group IS NOT NULL
    """)
    
    # Step 7c: Drop age_group column (will be calculated from birth_year)
    op.drop_column('customers', 'age_group')
    
    # Note: AgeGroup enum can remain in database for backward compatibility,
    # but the column is removed. The Customer model will calculate age_group
    # dynamically from birth_year via @property.


def downgrade():
    """
    Rollback to previous schema with crop_types table
    """
    
    # ================================================================
    # 1. RECREATE crop_types TABLE
    # ================================================================
    op.create_table(
        'crop_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_crop_types_id', 'crop_types', ['id'], unique=False)

    # ================================================================
    # 2. RESTORE crop_type_id COLUMN
    # ================================================================
    op.add_column(
        'customers',
        sa.Column('crop_type_id', sa.Integer(), nullable=True)
    )

    # Note: Restoring FK relationships requires re-seeding crop_types table
    # Manual steps needed:
    # 1. Run seeder to populate crop_types table
    # 2. Map crop_type strings back to crop_type_id integers
    # 3. Recreate foreign key constraint

    # WARNING: Data loss possible if new crops were added after migration
    # that don't exist in the restored crop_types table

    op.drop_column('customers', 'crop_type')

    # ================================================================
    # 3. REMOVE NEW COLUMNS
    # ================================================================
    op.drop_column('customers', 'gender')
    op.drop_column('customers', 'current_onboarding_field')

    # ================================================================
    # 4. CONVERT onboarding_attempts: JSON → Integer
    # ================================================================
    op.add_column(
        'customers',
        sa.Column(
            'onboarding_attempts_old',
            sa.Integer(),
            nullable=False,
            server_default='0'
        )
    )

    # Migrate data back - extract administration attempts
    op.execute("""
        UPDATE customers
        SET onboarding_attempts_old = 
            COALESCE((onboarding_attempts->>'administration')::integer, 0)
    """)

    op.drop_column('customers', 'onboarding_attempts')
    op.alter_column(
        'customers',
        'onboarding_attempts_old',
        new_column_name='onboarding_attempts'
    )

    # ================================================================
    # 5. CONVERT onboarding_candidates: JSON → Text
    # ================================================================
    op.add_column(
        'customers',
        sa.Column('onboarding_candidates_old', sa.Text(), nullable=True)
    )

    # Migrate data back - extract administration candidates as JSON text
    op.execute("""
        UPDATE customers
        SET onboarding_candidates_old = 
            CASE
                WHEN onboarding_candidates->>'administration' IS NOT NULL
                THEN (onboarding_candidates->'administration')::text
                ELSE NULL
            END
    """)

    op.drop_column('customers', 'onboarding_candidates')
    op.alter_column(
        'customers',
        'onboarding_candidates_old',
        new_column_name='onboarding_candidates'
    )

    # ================================================================
    # 6. DROP GENDER ENUM
    # ================================================================
    gender_enum = sa.Enum(name='gender')
    gender_enum.drop(op.get_bind(), checkfirst=True)
```

#### Post-Migration Steps

1. **Update crop_types router** (keep endpoint for mobile app):
   - Modify `backend/routers/crop_types.py` to read from config instead of database
   - Use array index + 1 as ID for backward compatibility (1-based indexing)
   - Example: `[{"id": 1, "name": "Cacao"}, {"id": 2, "name": "Avocado"}]`

2. **Remove crop_types seeder**:
   - Update `backend/seeder/__main__.py` to skip crop_types seeding

3. **Update relationships**:
   - Remove `crop_type` relationship from `Customer` model
   - Remove `CropType` class from `backend/models/customer.py`

4. **Verify no dependencies on crop_types table**:
   ```bash
   # Search for crop_types table references (excluding router)
   cd backend
   grep -r "CropType" --include="*.py" | grep -v "crop_types.py" | grep -v "# "
   grep -r "from models.customer import.*CropType" --include="*.py"
   ```

---

## Crop Types Configuration

Instead of using a database table, crop types are now defined in the main configuration file and validated using AI. This approach provides:

✅ **Simplicity**: No database migrations needed to add/remove crops  
✅ **Version Control**: Easy to track changes in git  
✅ **AI-Powered**: Handles spelling mistakes, translations, and variations automatically  
✅ **Performance**: No fuzzy matching needed, AI does the intelligent matching  
✅ **Flexibility**: Easy to add new crops by updating config only

### Crop Types in Main Config

**File**: `backend/config.template.json` (UPDATE EXISTING)

Add the crop types configuration section:

```json
{
  "crop_types": {
    "enabled_crops": ["Cacao", "Avocado"],
    "description": "List of supported crop types for farmer onboarding. AI will handle spelling variations and translations."
  }
}
```

**Benefits:**
- ✅ Single source of truth (no separate JSON file)
- ✅ Simple list of crop names (no aliases needed)
- ✅ AI handles all variations, spelling mistakes, and local names
- ✅ Easy to maintain and update

### Crop Types API Endpoint (Mobile Compatibility)

**File**: `backend/routers/crop_types.py` (UPDATE)

Update the existing endpoint to read from config instead of database:

```python
"""
Crop types router - reads from configuration instead of database.
Maintains backward compatibility with mobile app.
"""

from typing import List
from fastapi import APIRouter
from pydantic import BaseModel

from config import config

router = APIRouter(prefix="/crop-types", tags=["crop-types"])


class CropTypeInfo(BaseModel):
    """Crop type information for API response"""
    id: int
    name: str


@router.get("/", response_model=List[CropTypeInfo])
async def get_crop_types():
    """
    Get all enabled crop types.
    
    Reads from config.json instead of database.
    Uses array index + 1 as ID for backward compatibility.
    
    Returns:
        List[CropTypeInfo]: List of crop types with ID and name
    """
    enabled_crops = config.get("crop_types", {}).get(
        "enabled_crops", ["Cacao", "Avocado"]
    )
    
    # Use 1-based indexing for IDs (index + 1)
    return [
        CropTypeInfo(id=idx + 1, name=crop_name)
        for idx, crop_name in enumerate(enabled_crops)
    ]
```

**Key Changes:**
- ✅ Removed database dependency (`Session`, `CropType` model)
- ✅ Reads directly from `config.json`
- ✅ Uses array index + 1 as ID (1-based indexing)
- ✅ Maintains exact same response structure for mobile app
- ✅ No breaking changes to API contract

**Example Response:**
```json
[
  {"id": 1, "name": "Cacao"},
  {"id": 2, "name": "Avocado"}
]
```

**Note:** The `id` field is now virtual (derived from array index) and not stored anywhere. The Customer model stores only the crop name as a string.

### AI Crop Identification Service

**File**: `backend/services/ai_crop_identification.py` (NEW)

```python
"""
AI-powered crop identification service for farmer onboarding.

Uses OpenAI to intelligently match farmer input to known crop types,
handling spelling mistakes, translations (English/Swahili), and variations.
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field

from config import config

logger = logging.getLogger(__name__)


class CropIdentificationResult(BaseModel):
    """Result from crop identification"""
    match: bool = Field(description="Whether a crop was identified")
    crop_name: Optional[str] = Field(
        default=None,
        description="Matched crop name from the known crops list"
    )
    confidence: Optional[str] = Field(
        default=None,
        description="Confidence level: high, medium, low"
    )


class AICropIdentificationService:
    """Service for AI-powered crop identification"""

    def __init__(self, openai_service):
        """
        Initialize the crop identification service.
        
        Args:
            openai_service: OpenAI service instance
        """
        self.openai_service = openai_service
        self.known_crops = config.get("crop_types", {}).get(
            "enabled_crops", ["Cacao", "Avocado"]
        )

    async def detect_crop(
        self, text: str, language: str = "auto"
    ) -> CropIdentificationResult:
        """
        Detect crop type from farmer's text input.

        Uses OpenAI to intelligently match input against known crops,
        handling:
        - Spelling mistakes (e.g., "coco" → "Cacao")
        - Translations (e.g., "avokado" → "Avocado")
        - Local names (e.g., "chocolate tree" → "Cacao")
        - Variations (e.g., "cocoa" → "Cacao")

        Args:
            text: Farmer's message text
            language: Expected language (auto, en, sw)

        Returns:
            CropIdentificationResult with match status and crop name
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for crop detection")
            return CropIdentificationResult(match=False)

        # Build the prompt with known crops list
        known_crops_str = ", ".join(self.known_crops)
        
        system_prompt = f"""You are a crop identification expert for agricultural systems.

Your task: Identify if the farmer's message mentions any of these crops:
{known_crops_str}

Important rules:
1. Handle spelling mistakes (e.g., "coco" → "Cacao", "avokado" → "Avocado")
2. Recognize translations:
   - English: cacao, cocoa, avocado
   - Swahili: kakao, parachichi
3. Match local names (e.g., "chocolate tree" → "Cacao", "butter fruit" → "Avocado")
4. Return ONLY crops from the list above
5. If no crop is mentioned or crop is not in the list, return match=false
6. Return the standardized crop name from the list (exact spelling)

Examples:
- "I grow coco" → match=true, crop_name="Cacao"
- "We plant avokado" → match=true, crop_name="Avocado"
- "My farm has chocolate trees" → match=true, crop_name="Cacao"
- "I grow bananas" → match=false (not in list)
- "Hello" → match=false (no crop mentioned)
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]

        try:
            result = await self.openai_service.structured_output(
                messages=messages,
                response_model=CropIdentificationResult,
                temperature=0.0  # Deterministic matching
            )

            if result.match:
                # Validate that returned crop is in our list
                if result.crop_name not in self.known_crops:
                    logger.warning(
                        f"AI returned invalid crop: {result.crop_name}. "
                        f"Must be one of {self.known_crops}"
                    )
                    return CropIdentificationResult(match=False)

                logger.info(
                    f"Crop identified: '{result.crop_name}' from text: '{text}'"
                )
            else:
                logger.info(f"No crop match found in text: '{text}'")

            return result

        except Exception as e:
            logger.error(f"Error in crop detection: {e}", exc_info=True)
            return CropIdentificationResult(match=False)

    def get_known_crops(self) -> list[str]:
        """Get list of known/supported crops"""
        return self.known_crops.copy()


# ================================================================
# SERVICE FACTORY
# ================================================================

_service_instance = None


def get_ai_crop_service(openai_service) -> AICropIdentificationService:
    """
    Factory function to get AICropIdentificationService instance.
    
    Args:
        openai_service: OpenAI service instance
        
    Returns:
        AICropIdentificationService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = AICropIdentificationService(openai_service)
    return _service_instance
```

### Integration with Onboarding Service

Update the onboarding service to use AI crop identification:

```python
# backend/services/onboarding_service.py (UPDATE)
from services.ai_crop_identification import get_ai_crop_service

class OnboardingService:
    def __init__(self, db: Session):
        self.db = db
        self.openai_service = get_openai_service()
        self.fields_config = get_fields_by_priority()
        # Add AI crop service
        self.ai_crop_service = get_ai_crop_service(self.openai_service)

    async def extract_crop(self, message: str) -> str:
        """
        Extract crop name from message using AI.
        
        No need for structured extraction - AI service handles it.
        Just pass the message directly to AI crop service.
        """
        # Use AI crop identification service
        result = await self.ai_crop_service.detect_crop(message)
        
        if result.match and result.crop_name:
            return result.crop_name
        
        # If no match, return empty to trigger "no match" flow
        raise ValueError("No crop identified in message")

    def match_crop(
        self,
        crop_name: str,
        threshold: float
    ) -> List[Tuple[str, float]]:
        """
        Match crop name against known crops.
        
        Since AI already did the intelligent matching,
        we just need to validate and return.
        """
        known_crops = self.ai_crop_service.get_known_crops()
        
        if crop_name in known_crops:
            # Perfect match (AI already validated)
            return [(crop_name, 100.0)]
        
        # No match (shouldn't happen if extract_crop worked)
        return []
```

### Configuration Benefits

**Why this approach is better:**

1. **No Fuzzy Matching Needed**: AI understands context, not just string similarity
2. **Handles Translations**: AI knows "kakao" (Swahili) = "Cacao" (English)
3. **Handles Variations**: AI knows "cocoa" = "cacao" = "chocolate tree"
4. **Handles Typos**: AI can correct "coco" → "Cacao"
5. **Simple Configuration**: Just a list of crop names, no aliases needed
6. **Easy to Extend**: Add new crops to config, AI handles all variations automatically
7. **Language Agnostic**: Works with English, Swahili, or mixed input

### Adding New Crops

To add a new crop (e.g., "Mango"):

1. **Update config.template.json:**
```json
{
  "crop_types": {
    "enabled_crops": ["Cacao", "Avocado", "Mango"]
  }
}
```

2. **Update production config.json** (same change)

3. **Restart backend** (config is loaded on startup)

**That's it!** AI will automatically:
- Recognize "mango", "embe" (Swahili), "mango tree"
- Handle spelling mistakes like "manggo", "mnago"
- Match context like "I grow mango trees"

---

## Onboarding Configuration

### Configuration File

**File**: `backend/config/onboarding_fields.py` (NEW)

```python
"""
Onboarding fields configuration.

Define all profile fields to collect during farmer onboarding.
Fields are processed in priority order.
"""

from typing import List, Dict, Any, Optional, Literal

class OnboardingFieldConfig:
    """Configuration for a single onboarding field"""

    def __init__(
        self,
        field_name: str,
        db_field: Optional[str],
        required: bool,
        priority: int,
        initial_question: str,
        extraction_method: str,
        matching_method: Optional[str] = None,
        match_threshold: Optional[float] = None,
        ambiguity_threshold: Optional[float] = None,
        max_attempts: int = 3,
        field_type: Literal["fuzzy_match", "enum", "direct"] = "direct",
        success_message_template: Optional[str] = None,
    ):
        self.field_name = field_name
        self.db_field = db_field
        self.required = required
        self.priority = priority
        self.initial_question = initial_question
        self.extraction_method = extraction_method
        self.matching_method = matching_method
        self.match_threshold = match_threshold
        self.ambiguity_threshold = ambiguity_threshold
        self.max_attempts = max_attempts
        self.field_type = field_type
        self.success_message_template = success_message_template


# ONBOARDING FIELDS REGISTRY
ONBOARDING_FIELDS: List[OnboardingFieldConfig] = [

    # PRIORITY 1: Administration/Ward (REQUIRED)
    OnboardingFieldConfig(
        field_name="administration",
        db_field=None,  # Uses CustomerAdministrative relationship table
        required=True,
        priority=1,
        initial_question=(
            "Welcome! To help you better, I need to know where your farm is located. "
            "Please tell me your ward or area."
        ),
        extraction_method="extract_location",
        matching_method="match_administrative",
        match_threshold=60.0,
        ambiguity_threshold=15.0,
        max_attempts=3,
        field_type="fuzzy_match",
        success_message_template="Great! I've noted you're in {location_name}.",
    ),

    # PRIORITY 2: Crop Type (REQUIRED)
    OnboardingFieldConfig(
        field_name="crop_type",
        db_field="crop_type",  # Now a string field, not FK
        required=True,
        priority=2,
        initial_question="What type of crop do you grow on your farm? Please tell me your main crop.",
        extraction_method="extract_crop",
        matching_method="match_crop",
        match_threshold=70.0,
        ambiguity_threshold=15.0,
        max_attempts=3,
        field_type="fuzzy_match",
        success_message_template="Perfect! I've noted that you grow {crop_name}.",
    ),

    # PRIORITY 3: Gender (OPTIONAL)
    OnboardingFieldConfig(
        field_name="gender",
        db_field="gender",
        required=False,
        priority=3,
        initial_question=(
            "To help us serve you better, may I know your gender? "
            "(You can say: male, female, or other)"
        ),
        extraction_method="extract_gender",
        matching_method=None,  # Direct enum mapping
        max_attempts=2,
        field_type="enum",
        success_message_template="Thank you for sharing.",
    ),

    # PRIORITY 4: Birth Year (OPTIONAL)
    OnboardingFieldConfig(
        field_name="birth_year",
        db_field="birth_year",
        required=False,
        priority=4,
        initial_question=(
            "What year were you born? You can also tell me your age if that's easier.\n\n"
            "For example: '1980' or 'I'm 45 years old'"
        ),
        extraction_method="extract_birth_year",
        matching_method=None,  # AI converts age to birth year automatically
        max_attempts=2,
        field_type="integer",
        success_message_template="Got it, thank you!",
    ),
]


def get_field_config(field_name: str) -> Optional[OnboardingFieldConfig]:
    """Get configuration for specific field"""
    for config in ONBOARDING_FIELDS:
        if config.field_name == field_name:
            return config
    return None


def get_required_fields() -> List[OnboardingFieldConfig]:
    """Get all required fields"""
    return [f for f in ONBOARDING_FIELDS if f.required]


def get_optional_fields() -> List[OnboardingFieldConfig]:
    """Get all optional fields"""
    return [f for f in ONBOARDING_FIELDS if not f.required]


def get_fields_by_priority() -> List[OnboardingFieldConfig]:
    """Get all fields sorted by priority"""
    return sorted(ONBOARDING_FIELDS, key=lambda x: x.priority)
```

### Configuration Benefits

✅ **Add new fields** by appending to `ONBOARDING_FIELDS` list
✅ **Change priority** by updating `priority` value
✅ **Make fields optional** with `required=False`
✅ **Customize thresholds** per field type
✅ **No code changes** to service logic

---

## Refactored Onboarding Service

### Service Architecture

**File**: `backend/services/onboarding_service.py` (REFACTORED)

```python
"""
Generic onboarding service.

Handles collection of all farmer profile fields defined in onboarding_fields.py.
"""

import json
import logging
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Literal

from models.customer import (
    Customer, CustomerAdministrative,
    OnboardingStatus, Gender, AgeGroup
)
from models.administrative import Administrative
from services.openai_service import get_openai_service
from services.ai_crop_identification import get_ai_crop_service
from config.onboarding_fields import (
    ONBOARDING_FIELDS,
    OnboardingFieldConfig,
    get_field_config,
    get_fields_by_priority
)
from schemas.onboarding_schemas import OnboardingResponse

logger = logging.getLogger(__name__)


class OnboardingService:
    """Generic service for collecting all onboarding profile fields"""

    def __init__(self, db: Session):
        self.db = db
        self.openai_service = get_openai_service()
        self.fields_config = get_fields_by_priority()
        # Initialize AI crop identification service
        self.ai_crop_service = get_ai_crop_service(self.openai_service)

    # ================================================================
    # MAIN PUBLIC METHODS
    # ================================================================

    def needs_onboarding(self, customer: Customer) -> bool:
        """
        Check if customer needs onboarding (any required field incomplete).

        Returns:
            True if any required field is missing
            False if all required fields are complete
        """
        if customer.onboarding_status == OnboardingStatus.COMPLETED:
            return False

        # Check if there's a next incomplete field
        next_field = self._get_next_incomplete_field(customer)
        return next_field is not None

    async def process_onboarding_message(
        self,
        customer: Customer,
        message: str
    ) -> OnboardingResponse:
        """
        Main entry point for processing onboarding messages.

        Handles ANY onboarding field generically based on configuration.

        Flow:
        1. Get next incomplete field
        2. Check if awaiting selection (ambiguous match from previous message)
        3. Check if first message for this field → ask initial question
        4. Extract value from farmer's message
        5. Match/validate value (if field has matching logic)
        6. Save value or present options
        7. Move to next field or mark onboarding complete

        Args:
            customer: Customer instance
            message: Farmer's WhatsApp message text

        Returns:
            OnboardingResponse with status and message to send farmer
        """
        # Get next field that needs to be collected
        next_field_config = self._get_next_incomplete_field(customer)

        if next_field_config is None:
            # All required fields complete!
            return self._complete_onboarding(customer)

        field_name = next_field_config.field_name

        # Check if we're awaiting selection for this field (ambiguous match)
        if self._is_awaiting_selection(customer, field_name):
            return await self._process_selection(
                customer,
                message,
                next_field_config
            )

        # Check if this is the first message for this field
        if customer.current_onboarding_field != field_name:
            # Ask initial question
            return self._ask_initial_question(customer, next_field_config)

        # Process farmer's answer for this field
        return await self._process_field_value(
            customer,
            message,
            next_field_config
        )

    # ================================================================
    # FIELD COMPLETION CHECKS
    # ================================================================

    def _get_next_incomplete_field(
        self,
        customer: Customer
    ) -> Optional[OnboardingFieldConfig]:
        """
        Find the next field that needs to be collected (by priority order).

        Returns:
            OnboardingFieldConfig for next field, or None if all done
        """
        for field_config in self.fields_config:
            if not self._is_field_complete(customer, field_config):
                return field_config

        return None  # All fields complete

    def _is_field_complete(
        self,
        customer: Customer,
        field_config: OnboardingFieldConfig
    ) -> bool:
        """
        Check if a specific field is already filled.

        Args:
            customer: Customer instance
            field_config: Field configuration

        Returns:
            True if field is complete, False otherwise
        """
        field_name = field_config.field_name

        # Special case: administration uses relationship table
        if field_name == "administration":
            return self.db.query(CustomerAdministrative).filter_by(
                customer_id=customer.id
            ).count() > 0

        # Standard case: check Customer model field
        if field_config.db_field:
            field_value = getattr(customer, field_config.db_field)
            return field_value is not None

        return False

    # ================================================================
    # INITIAL QUESTION
    # ================================================================

    def _ask_initial_question(
        self,
        customer: Customer,
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Ask the initial question for a field.

        Updates customer state to track current field.
        """
        customer.current_onboarding_field = field_config.field_name
        customer.onboarding_status = OnboardingStatus.IN_PROGRESS
        self.db.commit()

        logger.info(
            f"Starting field collection: {field_config.field_name} "
            f"for customer {customer.id}"
        )

        return OnboardingResponse(
            status="in_progress",
            message=field_config.initial_question
        )

    # ================================================================
    # FIELD VALUE PROCESSING
    # ================================================================

    async def _process_field_value(
        self,
        customer: Customer,
        message: str,
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Extract and process field value from farmer's message.

        Generic handler for any field type:
        - fuzzy_match: Extract → Fuzzy match → Handle ambiguity/no match
        - enum: Extract → Validate → Save
        - direct: Extract → Save
        """
        field_name = field_config.field_name

        # Increment attempts
        self._increment_attempts(customer, field_name)

        # Check max attempts
        current_attempts = self._get_attempts(customer, field_name)
        if current_attempts > field_config.max_attempts:
            return self._handle_max_attempts(customer, field_config)

        # Extract value using field-specific extraction method
        try:
            extraction_method = getattr(self, field_config.extraction_method)
            extracted_value = await extraction_method(message)
        except Exception as e:
            logger.error(
                f"Extraction failed for {field_name}: {e}",
                exc_info=True
            )
            return OnboardingResponse(
                status="in_progress",
                message=(
                    f"I didn't quite understand that. "
                    f"{field_config.initial_question}"
                )
            )

        # Handle based on field type
        if field_config.field_type == "fuzzy_match":
            return await self._handle_fuzzy_match_field(
                customer,
                extracted_value,
                field_config
            )

        elif field_config.field_type == "enum":
            return self._handle_enum_field(
                customer,
                extracted_value,
                field_config
            )

        else:  # direct
            return self._handle_direct_field(
                customer,
                extracted_value,
                field_config
            )

    async def _handle_fuzzy_match_field(
        self,
        customer: Customer,
        extracted_value: Any,
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Handle fields that require fuzzy matching (administration, crop_type).

        Flow:
        1. Match against database
        2. No match → Create new (for crops) or ask again
        3. Ambiguous match → Present options
        4. Clear match → Save
        """
        # Get matching method
        matching_method = getattr(self, field_config.matching_method)

        # Perform fuzzy matching
        matches = matching_method(
            extracted_value,
            field_config.match_threshold
        )

        if not matches:
            # No match found
            return self._handle_no_match(
                customer,
                extracted_value,
                field_config
            )

        # Check for ambiguity
        if self._is_ambiguous_match(matches, field_config.ambiguity_threshold):
            return self._handle_ambiguous_match(
                customer,
                matches,
                field_config
            )

        # Clear match - save the top result
        return self._save_field_value(
            customer,
            matches[0][0],  # Top match object (CropType, Administrative, etc.)
            field_config
        )

    def _handle_enum_field(
        self,
        customer: Customer,
        extracted_value: str,
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Handle enum fields (gender, age_group).

        Direct mapping to enum value.
        """
        return self._save_field_value(
            customer,
            extracted_value,
            field_config
        )

    def _handle_direct_field(
        self,
        customer: Customer,
        extracted_value: Any,
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Handle direct fields (no matching needed).
        """
        return self._save_field_value(
            customer,
            extracted_value,
            field_config
        )

    # ================================================================
    # SAVING FIELD VALUES
    # ================================================================

    def _save_field_value(
        self,
        customer: Customer,
        value: Any,
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Save field value to database and move to next field.

        Generic save handler for any field type.
        """
        field_name = field_config.field_name

        try:
            # Special case: administration uses relationship table
            if field_name == "administration":
                # value is an Administrative object
                self._save_administration(customer, value)
                success_msg = field_config.success_message_template.format(
                    location_name=value.path
                )

            # Special case: crop_type (string value from AI identification)
            elif field_name == "crop_type":
                # value is already a string (crop name) from AI service
                customer.crop_type = value
                success_msg = field_config.success_message_template.format(
                    crop_name=value
                )

            # Special case: birth_year (integer value from AI extraction)
            elif field_name == "birth_year":
                # value is an integer (birth year) from extract_birth_year()
                customer.birth_year = value
                logger.info(f"Stored birth year {value} for customer {customer.id}")
                success_msg = field_config.success_message_template or "Thank you!"

            # Standard case: set Customer model field
            elif field_config.db_field:
                setattr(customer, field_config.db_field, value)
                success_msg = field_config.success_message_template or "Thank you!"

            else:
                logger.error(f"No save logic for field: {field_name}")
                success_msg = "Thank you!"

            # Clear field-specific state
            self._clear_field_state(customer, field_name)

            # Commit changes
            self.db.commit()

            logger.info(
                f"Saved {field_name} for customer {customer.id}: {value}"
            )

            # Check if there are more fields
            next_field = self._get_next_incomplete_field(customer)

            if next_field:
                # More fields to collect - ask next question
                return self._ask_initial_question(customer, next_field)
            else:
                # All fields complete!
                return self._complete_onboarding(customer)

        except Exception as e:
            logger.error(
                f"Failed to save {field_name}: {e}",
                exc_info=True
            )
            self.db.rollback()

            return OnboardingResponse(
                status="in_progress",
                message=(
                    "Sorry, I had trouble saving that information. "
                    "Please try again."
                )
            )

    def _save_administration(self, customer: Customer, administrative: Administrative):
        """Save administration/ward to CustomerAdministrative table"""
        # Check if already exists
        existing = self.db.query(CustomerAdministrative).filter_by(
            customer_id=customer.id
        ).first()

        if existing:
            existing.administrative_id = administrative.id
        else:
            customer_admin = CustomerAdministrative(
                customer_id=customer.id,
                administrative_id=administrative.id
            )
            self.db.add(customer_admin)

    # ================================================================
    # AMBIGUOUS MATCH HANDLING
    # ================================================================

    def _is_ambiguous_match(
        self,
        matches: List[Tuple[Any, float]],
        ambiguity_threshold: float
    ) -> bool:
        """
        Check if top 2 matches are too close (ambiguous).

        Args:
            matches: List of (object, score) tuples sorted by score desc
            ambiguity_threshold: Max score difference for ambiguity

        Returns:
            True if ambiguous (top 2 within threshold)
        """
        if len(matches) < 2:
            return False

        top_score = matches[0][1]
        second_score = matches[1][1]

        return (top_score - second_score) < ambiguity_threshold

    def _handle_ambiguous_match(
        self,
        customer: Customer,
        matches: List[Tuple[Any, float]],
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Handle ambiguous matches by presenting options to farmer.

        Stores candidate IDs in onboarding_candidates JSON.
        """
        field_name = field_config.field_name

        # Take top N candidates
        candidates = [m[0] for m in matches[:5]]  # Max 5 options

        # Store candidate IDs in JSON
        self._store_candidates(customer, field_name, candidates)

        # Build options message
        options_message = self._build_options_message(
            candidates,
            field_name
        )

        self.db.commit()

        logger.info(
            f"Ambiguous match for {field_name}, "
            f"presenting {len(candidates)} options"
        )

        return OnboardingResponse(
            status="awaiting_selection",
            message=options_message
        )

    def _store_candidates(
        self,
        customer: Customer,
        field_name: str,
        candidates: List[Any]
    ):
        """Store candidate values in onboarding_candidates JSON"""
        # Get current candidates dict
        candidates_dict = json.loads(customer.onboarding_candidates or "{}")

        # Extract values from candidates
        # For administration: extract IDs from objects
        # For crop_type: candidates are already strings
        if field_name == "administration":
            candidate_values = [c.id for c in candidates]
        elif field_name == "crop_type":
            # Candidates are already crop name strings
            candidate_values = candidates
        else:
            # Generic: try to get id or use string representation
            candidate_values = [getattr(c, 'id', str(c)) for c in candidates]

        # Store for this field
        candidates_dict[field_name] = candidate_values

        # Save back to JSON
        customer.onboarding_candidates = json.dumps(candidates_dict)

    def _build_options_message(
        self,
        candidates: List[Any],
        field_name: str
    ) -> str:
        """Build numbered options message for farmer"""
        if field_name == "administration":
            # Administrative has 'path' attribute (e.g., "Kenya > Nairobi > Central")
            message = "I found several locations that match. Please select the number:\n\n"
            for i, candidate in enumerate(candidates, 1):
                message += f"{i}. {candidate.path}\n"

        elif field_name == "crop_type":
            # Crop names are strings from AI identification
            message = "I found several crops that match. Please select the number:\n\n"
            for i, candidate in enumerate(candidates, 1):
                message += f"{i}. {candidate}\n"

        else:
            # Generic fallback
            message = "Please select the number:\n\n"
            for i, candidate in enumerate(candidates, 1):
                message += f"{i}. {getattr(candidate, 'name', str(candidate))}\n"

        message += f"\nReply with the number (1-{len(candidates)})."

        return message

    async def _process_selection(
        self,
        customer: Customer,
        message: str,
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Process farmer's numeric selection from ambiguous options.

        Parses message for number (1, 2, 3) or ordinal words (first, second).
        """
        field_name = field_config.field_name

        # Parse selection
        selection_index = self._parse_selection(message)

        if selection_index is None:
            # Invalid selection
            return OnboardingResponse(
                status="awaiting_selection",
                message=(
                    "I didn't understand your selection. "
                    "Please reply with a number (1, 2, 3, etc.)."
                )
            )

        # Get candidates from JSON
        candidates_dict = json.loads(customer.onboarding_candidates or "{}")
        candidate_ids = candidates_dict.get(field_name, [])

        if selection_index < 1 or selection_index > len(candidate_ids):
            # Out of range
            return OnboardingResponse(
                status="awaiting_selection",
                message=(
                    f"Please select a number between 1 and {len(candidate_ids)}."
                )
            )

        # Get selected candidate (convert to 0-indexed)
        selected_value = candidate_ids[selection_index - 1]

        # Fetch object from database or use value directly
        if field_name == "administration":
            # For administration, candidate_ids contains DB IDs
            selected_obj = self.db.query(Administrative).get(selected_value)
            if not selected_obj:
                logger.error(f"Administrative {selected_value} not found")
                return OnboardingResponse(
                    status="in_progress",
                    message="Sorry, something went wrong. Please try again."
                )
        elif field_name == "crop_type":
            # For crop_type, candidate_ids contains crop name strings
            selected_obj = selected_value
        else:
            logger.error(f"Unknown field for selection: {field_name}")
            return OnboardingResponse(
                status="in_progress",
                message="Sorry, something went wrong. Please try again."
            )

        # Save the selected value
        return self._save_field_value(customer, selected_obj, field_config)

    def _parse_selection(self, message: str) -> Optional[int]:
        """
        Parse numeric selection from message.

        Accepts:
        - Direct numbers: "1", "2", "3"
        - Ordinal words: "first", "second", "third"
        - Phrases: "number 2", "option 1"

        Returns:
            Integer (1-indexed) or None if invalid
        """
        import re

        message_lower = message.strip().lower()

        # Try direct number
        match = re.search(r'\b(\d+)\b', message_lower)
        if match:
            return int(match.group(1))

        # Try ordinal words
        ordinals = {
            "first": 1, "1st": 1,
            "second": 2, "2nd": 2,
            "third": 3, "3rd": 3,
            "fourth": 4, "4th": 4,
            "fifth": 5, "5th": 5,
        }

        for word, number in ordinals.items():
            if word in message_lower:
                return number

        return None

    # ================================================================
    # NO MATCH HANDLING
    # ================================================================

    def _handle_no_match(
        self,
        customer: Customer,
        extracted_value: Any,
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Handle case when no match found.

        For crops: Should not happen (AI already validated), but ask again
        For administration: Ask again
        """
        field_name = field_config.field_name

        # For all fields: ask again
        # Note: For crops, this shouldn't happen because AI validates against known crops
        return OnboardingResponse(
            status="in_progress",
            message=(
                f"I couldn't find a match for that. "
                f"{field_config.initial_question}"
            )
        )

    # ================================================================
    # MAX ATTEMPTS HANDLING
    # ================================================================

    def _handle_max_attempts(
        self,
        customer: Customer,
        field_config: OnboardingFieldConfig
    ) -> OnboardingResponse:
        """
        Handle max attempts exceeded.

        For required fields: Skip for now, can be collected later
        For optional fields: Skip and move to next
        """
        field_name = field_config.field_name

        logger.warning(
            f"Max attempts exceeded for {field_name}, "
            f"customer {customer.id}"
        )

        # Clear field state
        self._clear_field_state(customer, field_name)

        # Mark field as failed (in attempts JSON)
        attempts_dict = json.loads(customer.onboarding_attempts or "{}")
        attempts_dict[f"{field_name}_failed"] = True
        customer.onboarding_attempts = json.dumps(attempts_dict)

        self.db.commit()

        if field_config.required:
            # Skip required field for now
            # Check if there are more fields
            next_field = self._get_next_incomplete_field(customer)

            if next_field:
                # Continue with next field
                return self._ask_initial_question(customer, next_field)
            else:
                # No more fields - complete onboarding anyway
                return self._complete_onboarding(customer)

        else:
            # Optional field - skip it
            next_field = self._get_next_incomplete_field(customer)

            if next_field:
                return self._ask_initial_question(customer, next_field)
            else:
                return self._complete_onboarding(customer)

    # ================================================================
    # ONBOARDING COMPLETION
    # ================================================================

    def _complete_onboarding(self, customer: Customer) -> OnboardingResponse:
        """
        Mark onboarding as complete.

        All required fields have been collected.
        """
        customer.onboarding_status = OnboardingStatus.COMPLETED
        customer.current_onboarding_field = None
        self.db.commit()

        logger.info(f"Onboarding completed for customer {customer.id}")

        return OnboardingResponse(
            status="completed",
            message=(
                "Thank you! Your profile is complete. "
                "How can I help you with your farm today?"
            )
        )

    # ================================================================
    # STATE MANAGEMENT HELPERS
    # ================================================================

    def _is_awaiting_selection(
        self,
        customer: Customer,
        field_name: str
    ) -> bool:
        """Check if customer is selecting from ambiguous options"""
        if not customer.onboarding_candidates:
            return False

        candidates_dict = json.loads(customer.onboarding_candidates)
        return field_name in candidates_dict and len(candidates_dict[field_name]) > 0

    def _increment_attempts(self, customer: Customer, field_name: str):
        """Increment attempt counter for field"""
        attempts_dict = json.loads(customer.onboarding_attempts or "{}")
        attempts_dict[field_name] = attempts_dict.get(field_name, 0) + 1
        customer.onboarding_attempts = json.dumps(attempts_dict)
        self.db.commit()

    def _get_attempts(self, customer: Customer, field_name: str) -> int:
        """Get attempt count for field"""
        if not customer.onboarding_attempts:
            return 0
        attempts_dict = json.loads(customer.onboarding_attempts)
        return attempts_dict.get(field_name, 0)

    def _clear_field_state(self, customer: Customer, field_name: str):
        """Clear field-specific state from JSON fields"""
        # Clear candidates
        if customer.onboarding_candidates:
            candidates_dict = json.loads(customer.onboarding_candidates)
            candidates_dict.pop(field_name, None)
            customer.onboarding_candidates = json.dumps(candidates_dict) if candidates_dict else None

        # Don't clear attempts - keep for analytics

    # ================================================================
    # FIELD-SPECIFIC EXTRACTION METHODS
    # ================================================================

    async def extract_location(self, message: str) -> dict:
        """
        Extract location (province, district, ward) from message.

        EXISTING IMPLEMENTATION - Keep as is.
        """
        # ... existing OpenAI extraction logic ...
        pass

    async def extract_crop(self, message: str) -> str:
        """
        Extract crop name from message.

        Examples:
        - "I grow cacao" → "cacao"
        - "Avocado" → "avocado"
        - "We plant chocolate trees" → "cacao"
        """
        class CropExtraction(BaseModel):
            crop_name: str = Field(description="Main crop mentioned by farmer")

        system_prompt = """Extract the MAIN crop type from the farmer's message.
        Use local crop names when appropriate (e.g., "kakao" for cacao).
        Examples:
        - "I grow cacao" → "cacao"
        - "Avocado and bananas" → "avocado"
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        extraction = await self.openai_service.structured_output(
            messages=messages,
            response_model=CropExtraction
        )

        return extraction.crop_name.strip().title()

    async def extract_gender(self, message: str) -> str:
        """
        Extract gender from message.

        Maps to Gender enum.
        """
        class GenderExtraction(BaseModel):
            gender: Literal["male", "female", "other"]

        system_prompt = """Extract gender from the farmer's message.
        Map to one of: male, female, other
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        extraction = await self.openai_service.structured_output(
            messages=messages,
            response_model=GenderExtraction
        )

        return extraction.gender

    async def extract_age_group(self, message: str) -> tuple[str, Optional[int]]:
        """
        Extract age group and exact age from message.

        Handles various input formats:
        - Numbers: "1", "2", "3" → maps to age groups
        - Ranges: "20-35", "36-50", "51+" → direct mapping
        - Specific ages: "25", "45", "60" → infers group AND stores exact age
        - Text: "young", "middle-aged", "senior" → maps to group
        
        Maps to AgeGroup enum (20-35, 36-50, 51+) and extracts exact age when available.
        
        Returns:
            tuple: (age_group, exact_age) where exact_age is None if not provided
        
        Examples:
        - "1" → ("20-35", None)
        - "45" → ("36-50", 45)
        - "I'm 60 years old" → ("51+", 60)
        - "young farmer" → ("20-35", None)
        """
        class AgeGroupExtraction(BaseModel):
            age_group: Literal["20-35", "36-50", "51+"]
            exact_age: Optional[int] = Field(
                default=None,
                description="The exact age if mentioned (e.g., 25, 45, 60). None if only group/range provided."
            )

        system_prompt = """Extract age group and exact age from the farmer's message.

Your task: 
1. Map to one of these age groups: "20-35", "36-50", "51+"
2. Extract exact age if provided (set to null if not mentioned)

Handle these input formats:
1. Numeric selections: 1 → "20-35", 2 → "36-50", 3 → "51+"
   - exact_age: null (only selection number, not actual age)
2. Age ranges: "20-35", "36-50", "51+" → use as-is
   - exact_age: null (range provided, not specific age)
3. Specific ages: "25", "45", "60"
   - age_group: infer from age (25 → "20-35", 45 → "36-50", 60 → "51+")
   - exact_age: the number provided (25, 45, 60)
4. Descriptive text:
   - "young", "youth" → "20-35", exact_age: null
   - "middle", "middle-aged" → "36-50", exact_age: null
   - "old", "senior", "elder" → "51+", exact_age: null
5. Sentences: "I am 45 years old"
   - age_group: "36-50"
   - exact_age: 45

Examples:
- "1" → age_group: "20-35", exact_age: null
- "2" → age_group: "36-50", exact_age: null
- "36-50" → age_group: "36-50", exact_age: null
- "I'm 25" → age_group: "20-35", exact_age: 25
- "45 years" → age_group: "36-50", exact_age: 45
- "I'm 60" → age_group: "51+", exact_age: 60
- "young farmer" → age_group: "20-35", exact_age: null
- "senior" → age_group: "51+", exact_age: null
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        extraction = await self.openai_service.structured_output(
            messages=messages,
            response_model=AgeGroupExtraction
        )

        return extraction.age_group, extraction.exact_age

    async def extract_birth_year(self, message: str) -> int:
        """
        Extract birth year from message.

        Handles various input formats:
        - Birth year: "1980", "1995", "2000"
        - Current age: "45", "I'm 25 years old", "thirty years"
        - Age ranges: "I'm in my 40s" → approximates to midpoint
        
        Converts age to birth year automatically using current year.
        
        Returns:
            int: Birth year (e.g., 1980)
        
        Examples:
        - "1980" → 1980
        - "I'm 45" → 2025 - 45 = 1980
        - "25 years old" → 2025 - 25 = 2000
        - "in my 40s" → 2025 - 43 = 1982 (midpoint of 40-49)
        """
        from datetime import datetime
        
        class BirthYearExtraction(BaseModel):
            birth_year: int = Field(
                description="Birth year extracted or calculated from age (e.g., 1980, 1995, 2000)"
            )

        current_year = datetime.now().year
        
        system_prompt = f"""Extract or calculate birth year from the farmer's message.

Current year: {current_year}

Your task: 
Extract birth year or calculate it from age.

Handle these input formats:
1. Birth year directly: "1980", "I was born in 1995" → use the year
2. Current age: "45", "I'm 25 years old", "I am thirty"
   - Calculate: birth_year = {current_year} - age
   - Example: "I'm 45" → {current_year} - 45 = {current_year - 45}
3. Age range: "in my 40s", "mid-thirties"
   - Use midpoint of range
   - "in my 40s" → assume age 43 → {current_year} - 43 = {current_year - 43}
   - "mid-thirties" → assume age 35 → {current_year} - 35 = {current_year - 35}
4. Descriptive text:
   - "young" → assume age 27 → {current_year} - 27
   - "middle-aged" → assume age 43 → {current_year} - 43
   - "senior", "old" → assume age 60 → {current_year} - 60

Validation:
- Birth year must be between 1920 and {current_year - 18} (farmers should be 18+)
- If calculated birth year is invalid, use reasonable default based on context

Examples:
- "1980" → birth_year: 1980
- "I'm 45" → birth_year: {current_year - 45}
- "25 years old" → birth_year: {current_year - 25}
- "born in 1995" → birth_year: 1995
- "I'm in my 40s" → birth_year: {current_year - 43}
- "young farmer" → birth_year: {current_year - 27}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        extraction = await self.openai_service.structured_output(
            messages=messages,
            response_model=BirthYearExtraction
        )

        return extraction.birth_year

    # ================================================================
    # FIELD-SPECIFIC MATCHING METHODS
    # ================================================================

    def match_administrative(
        self,
        location: dict,
        threshold: float
    ) -> List[Tuple[Administrative, float]]:
        """
        Fuzzy match location against administrative table.

        EXISTING IMPLEMENTATION - Keep as is.
        """
        # ... existing fuzzy matching logic ...
        pass

    def match_crop(
        self,
        crop_name: str,
        threshold: float
    ) -> List[Tuple[str, float]]:
        """
        Match crop name against known crops from config.

        Since AI already did intelligent matching, we just validate
        against the known crops list.

        Returns:
            List of (crop_name, score) - single item if matched, empty if not
        """
        known_crops = self.ai_crop_service.get_known_crops()

        # Check if crop name matches any known crop (case-insensitive)
        for known_crop in known_crops:
            if crop_name.lower() == known_crop.lower():
                # Perfect match - return as tuple with 100% score
                return [(known_crop, 100.0)]

        # No match found
        return []


# ================================================================
# SERVICE FACTORY
# ================================================================

from functools import lru_cache

@lru_cache()
def get_onboarding_service(db: Session) -> OnboardingService:
    """Factory function to get OnboardingService instance"""
    return OnboardingService(db)
```

---

## Integration (No Changes!)

The webhook code **remains unchanged** because the service interface is the same:

**File**: `backend/routers/whatsapp.py` (lines 181-234)

```python
# Phase 3: AI ONBOARDING (administration question)
onboarding_service = get_onboarding_service(db)

if onboarding_service.needs_onboarding(customer):
    # Check if awaiting selection (previous ambiguous match)
    if (customer.onboarding_status == OnboardingStatus.IN_PROGRESS
        and customer.onboarding_candidates):
        # Process farmer's selection from multiple options
        onboarding_response = await onboarding_service.process_selection(customer, Body)
    else:
        # Extract location from farmer's message
        onboarding_response = await onboarding_service.process_location_message(customer, Body)

    # Send onboarding response to farmer
    whatsapp_service.send_message(phone_number, onboarding_response.message)

    # If still in progress, don't continue to regular message flow
    if onboarding_response.status in ["in_progress", "awaiting_selection"]:
        return {"status": "success", "message": "Onboarding in progress"}
```

**BECOMES** (simplified):

```python
# Phase 3: GENERIC ONBOARDING (all profile fields)
onboarding_service = get_onboarding_service(db)

if onboarding_service.needs_onboarding(customer):
    # Generic handler for ANY field
    onboarding_response = await onboarding_service.process_onboarding_message(
        customer,
        Body
    )

    # Send response to farmer
    whatsapp_service.send_message(phone_number, onboarding_response.message)

    # Create message record
    message_service.create_message(
        customer_id=customer.id,
        body=onboarding_response.message,
        from_source=MessageFrom.BOT.value,
        message_sid=f"onboarding_{customer.id}_{int(time.time())}",
        delivery_status=DeliveryStatus.DELIVERED,
        message_type=MessageType.TEXT
    )

    # If still in progress, stop here
    if onboarding_response.status in ["in_progress", "awaiting_selection"]:
        return {"status": "success", "message": "Onboarding in progress"}

# Phase 4: Regular message flow (ticket checking, WHISPER/REPLY, etc.)
# ... existing code ...
```

---

## Testing Strategy

### Test File Structure

```
backend/tests/
├── test_onboarding_service.py          # Main service tests
├── test_onboarding_administration.py   # Administration field tests
├── test_onboarding_crop.py             # Crop field tests
├── test_onboarding_gender.py           # Gender field tests
├── test_onboarding_age_group.py        # Age group field tests
└── test_onboarding_integration.py      # Full flow tests
```

### Key Test Scenarios

**File**: `backend/tests/test_onboarding_service.py`

```python
import pytest
from models.customer import Customer, OnboardingStatus
from services.onboarding_service import OnboardingService

# ================================================================
# FIELD PRIORITY TESTS
# ================================================================

def test_administration_is_first_priority(onboarding_service, customer):
    """Administration field should be collected first"""
    next_field = onboarding_service._get_next_incomplete_field(customer)
    assert next_field.field_name == "administration"

def test_crop_type_after_administration(onboarding_service, customer_with_admin):
    """Crop type should be second priority after administration"""
    next_field = onboarding_service._get_next_incomplete_field(customer_with_admin)
    assert next_field.field_name == "crop_type"

def test_gender_after_crop(onboarding_service, customer_with_admin_and_crop):
    """Gender should be third priority"""
    next_field = onboarding_service._get_next_incomplete_field(customer_with_admin_and_crop)
    assert next_field.field_name == "gender"

# ================================================================
# NEEDS ONBOARDING TESTS
# ================================================================

def test_needs_onboarding_when_no_fields(onboarding_service, customer):
    """Should need onboarding when no fields collected"""
    assert onboarding_service.needs_onboarding(customer) is True

def test_needs_onboarding_when_partial(onboarding_service, customer_with_admin):
    """Should need onboarding when some fields missing"""
    assert onboarding_service.needs_onboarding(customer_with_admin) is True

def test_no_onboarding_when_complete(onboarding_service, customer_complete):
    """Should not need onboarding when all required fields filled"""
    assert onboarding_service.needs_onboarding(customer_complete) is False

# ================================================================
# GENERIC FLOW TESTS
# ================================================================

@pytest.mark.asyncio
async def test_asks_initial_question_for_new_field(onboarding_service, customer):
    """Should ask initial question when starting new field"""
    response = await onboarding_service.process_onboarding_message(
        customer,
        "Hello"
    )

    assert response.status == "in_progress"
    assert "where your farm is located" in response.message.lower()
    assert customer.current_onboarding_field == "administration"

@pytest.mark.asyncio
async def test_processes_field_value(onboarding_service, customer):
    """Should process field value after initial question"""
    # Set up: customer is being asked for administration
    customer.current_onboarding_field = "administration"
    customer.onboarding_status = OnboardingStatus.IN_PROGRESS

    response = await onboarding_service.process_onboarding_message(
        customer,
        "I am in Nairobi, Westlands ward"
    )

    # Should either save or present options
    assert response.status in ["in_progress", "awaiting_selection", "completed"]

@pytest.mark.asyncio
async def test_moves_to_next_field_after_save(
    onboarding_service,
    customer_with_admin
):
    """Should automatically ask next field after saving current field"""
    response = await onboarding_service.process_onboarding_message(
        customer_with_admin,
        "I grow cacao"  # Answering crop question
    )

    # Should move to crop question or gender (depending on what's complete)
    assert response.status == "in_progress"

# ================================================================
# AMBIGUOUS MATCH TESTS
# ================================================================

@pytest.mark.asyncio
async def test_presents_options_for_ambiguous_match(
    onboarding_service,
    customer,
    multiple_similar_wards
):
    """Should present numbered options when match is ambiguous"""
    customer.current_onboarding_field = "administration"

    response = await onboarding_service.process_onboarding_message(
        customer,
        "Westlands"  # Multiple wards named Westlands
    )

    assert response.status == "awaiting_selection"
    assert "1." in response.message
    assert "2." in response.message

@pytest.mark.asyncio
async def test_processes_numeric_selection(
    onboarding_service,
    customer_awaiting_selection
):
    """Should process numeric selection from options"""
    response = await onboarding_service.process_onboarding_message(
        customer_awaiting_selection,
        "2"
    )

    # Should save selection and move to next field
    assert response.status in ["in_progress", "completed"]

# ================================================================
# MAX ATTEMPTS TESTS
# ================================================================

@pytest.mark.asyncio
async def test_skips_field_after_max_attempts(
    onboarding_service,
    customer
):
    """Should skip field after max attempts exceeded"""
    customer.current_onboarding_field = "gender"
    customer.onboarding_attempts = json.dumps({"gender": 3})

    response = await onboarding_service.process_onboarding_message(
        customer,
        "unclear message"
    )

    # Should move to next field or complete
    assert customer.current_onboarding_field != "gender"

# ================================================================
# COMPLETION TESTS
# ================================================================

@pytest.mark.asyncio
async def test_completes_onboarding_when_all_required_filled(
    onboarding_service,
    customer_with_admin_and_crop
):
    """Should mark onboarding complete when all required fields filled"""
    # Only administration and crop are required
    # Gender and age_group are optional

    next_field = onboarding_service._get_next_incomplete_field(customer_with_admin_and_crop)

    if next_field is None or not next_field.required:
        # Should complete onboarding
        response = await onboarding_service.process_onboarding_message(
            customer_with_admin_and_crop,
            "test message"
        )

        assert customer_with_admin_and_crop.onboarding_status == OnboardingStatus.COMPLETED

# ================================================================
# BIRTH YEAR EXTRACTION TESTS
# ================================================================

@pytest.mark.asyncio
async def test_extract_birth_year_from_year(onboarding_service):
    """Should extract birth year when year is provided directly"""
    birth_year = await onboarding_service.extract_birth_year("1980")
    
    assert birth_year == 1980

@pytest.mark.asyncio
async def test_extract_birth_year_from_age(onboarding_service):
    """Should calculate birth year from age"""
    from datetime import datetime
    current_year = datetime.now().year
    
    birth_year = await onboarding_service.extract_birth_year("I'm 45 years old")
    
    expected_birth_year = current_year - 45
    assert birth_year == expected_birth_year

@pytest.mark.asyncio
async def test_extract_birth_year_from_age_range(onboarding_service):
    """Should approximate birth year from age range"""
    from datetime import datetime
    current_year = datetime.now().year
    
    birth_year = await onboarding_service.extract_birth_year("I'm in my 40s")
    
    # Should use midpoint of range (43)
    expected_birth_year = current_year - 43
    assert abs(birth_year - expected_birth_year) <= 5  # Allow some variance

@pytest.mark.asyncio
async def test_stores_birth_year(onboarding_service, customer, db_session):
    """Should store birth year in database"""
    customer.current_onboarding_field = "birth_year"
    db_session.add(customer)
    db_session.commit()
    
    # Simulate saving birth year
    from config.onboarding_fields import get_field_config
    birth_year_config = get_field_config("birth_year")
    
    response = onboarding_service._save_field_value(
        customer,
        1980,  # Birth year
        birth_year_config
    )
    
    db_session.refresh(customer)
    assert customer.birth_year == 1980

@pytest.mark.asyncio
async def test_age_calculated_from_birth_year(customer, db_session):
    """Should calculate current age from birth year"""
    from datetime import datetime
    
    customer.birth_year = 1980
    db_session.add(customer)
    db_session.commit()
    
    current_year = datetime.now().year
    expected_age = current_year - 1980
    
    assert customer.age == expected_age

@pytest.mark.asyncio
async def test_age_group_calculated_from_birth_year(customer, db_session):
    """Should calculate age group from birth year"""
    from datetime import datetime
    
    current_year = datetime.now().year
    
    # Test young farmer (20-35)
    customer.birth_year = current_year - 25
    assert customer.age_group == "20-35"
    
    # Test middle-aged farmer (36-50)
    customer.birth_year = current_year - 45
    assert customer.age_group == "36-50"
    
    # Test senior farmer (51+)
    customer.birth_year = current_year - 60
    assert customer.age_group == "51+"

# ================================================================
# STATE MANAGEMENT TESTS
# ================================================================

def test_increments_attempts(onboarding_service, customer):
    """Should increment attempts counter"""
    onboarding_service._increment_attempts(customer, "crop_type")

    attempts = onboarding_service._get_attempts(customer, "crop_type")
    assert attempts == 1

def test_stores_candidates_in_json(onboarding_service, customer, crops):
    """Should store candidates in JSON format"""
    onboarding_service._store_candidates(customer, "crop_type", crops[:3])

    candidates_dict = json.loads(customer.onboarding_candidates)
    assert "crop_type" in candidates_dict
    assert len(candidates_dict["crop_type"]) == 3

def test_clears_field_state(onboarding_service, customer):
    """Should clear field-specific state"""
    customer.onboarding_candidates = json.dumps({"crop_type": [1, 2, 3]})

    onboarding_service._clear_field_state(customer, "crop_type")

    candidates_dict = json.loads(customer.onboarding_candidates or "{}")
    assert "crop_type" not in candidates_dict
```

---

## Implementation Checklist

### Phase 1: Database Schema
- [ ] Update `Customer` model in `backend/models/customer.py`
  - [ ] Change `onboarding_candidates` from Text to JSON
  - [ ] Change `onboarding_attempts` from Integer to JSON
  - [ ] Add `current_onboarding_field` String column
  - [ ] Change `crop_type_id` FK to `crop_type` String
  - [ ] Add `Gender` enum
  - [ ] Add `gender` column (nullable)
  - [ ] Verify `age_group` column exists
  - [ ] Remove `CropType` model class
- [ ] Create Alembic migration script
- [ ] Test migration on development database
- [ ] Verify data migration (old format → new format)
- [ ] Update `backend/routers/crop_types.py` to read from config instead of database

### Phase 2: Configuration
- [ ] Create `backend/config/onboarding_fields.py`
- [ ] Define `OnboardingFieldConfig` class
- [ ] Define `ONBOARDING_FIELDS` list with all 4 fields
- [ ] Add helper functions (`get_field_config`, etc.)

### Phase 3: Service Refactoring
- [ ] Backup current `onboarding_service.py`
- [ ] Refactor `OnboardingService` class
  - [ ] Update `needs_onboarding()` method
  - [ ] Replace `process_location_message()` with generic `process_onboarding_message()`
  - [ ] Implement `_get_next_incomplete_field()`
  - [ ] Implement `_is_field_complete()`
  - [ ] Implement `_process_field_value()` (generic)
  - [ ] Implement `_handle_fuzzy_match_field()`
  - [ ] Implement `_handle_enum_field()`
  - [ ] Add new extraction methods (`extract_crop`, `extract_gender`, `extract_birth_year`)
  - [ ] Add new matching method (`match_crop`)
  - [ ] Update state management methods to use JSON
- [ ] Update `OnboardingResponse` schema if needed

### Phase 4: Integration
- [ ] Update `backend/routers/whatsapp.py`
  - [ ] Simplify onboarding check (lines 181-234)
  - [ ] Use new `process_onboarding_message()` method
  - [ ] Remove old field-specific logic
- [ ] Test integration with existing flow

### Phase 5: Testing
- [ ] Create test fixtures
- [ ] Write unit tests for each method
- [ ] Write integration tests for full flows
- [ ] Test priority ordering
- [ ] Test ambiguous matches for each field type
- [ ] Test max attempts handling
- [ ] Run full test suite: `./dc.sh exec backend pytest -v`
- [ ] Achieve 90%+ coverage

### Phase 6: Manual Testing
- [ ] Test complete onboarding flow (all 4 fields)
- [ ] Test administration collection (existing flow)
- [ ] Test crop type collection (new)
- [ ] Test gender collection (new)
- [ ] Test age group collection (new)
- [ ] Test ambiguous matches for crops
- [ ] Test max attempts scenarios
- [ ] Test optional field skipping
- [ ] Verify normal conversation flow after completion

### Phase 7: Documentation
- [ ] Update inline code comments
- [ ] Update `CLAUDE.md` with new onboarding system
- [ ] Create admin documentation for adding new fields
- [ ] Update API documentation

---

## Adding New Fields (Future)

To add a new profile field (e.g., "farm_size"), simply:

### 1. Add Database Column (if needed)

```python
# backend/models/customer.py
class Customer(Base):
    farm_size = Column(Float, nullable=True)  # Hectares
```

### 2. Add Field to Configuration

```python
# backend/config/onboarding_fields.py

ONBOARDING_FIELDS.append(
    OnboardingFieldConfig(
        field_name="farm_size",
        db_field="farm_size",
        required=False,
        priority=5,
        initial_question="How large is your farm in hectares?",
        extraction_method="extract_farm_size",
        matching_method=None,
        max_attempts=2,
        field_type="direct",
        success_message_template="Thank you! I've noted your farm is {farm_size} hectares.",
    )
)
```

### 3. Add Extraction Method

```python
# backend/services/onboarding_service.py

async def extract_farm_size(self, message: str) -> float:
    """Extract farm size from message"""
    class FarmSizeExtraction(BaseModel):
        farm_size: float = Field(description="Farm size in hectares")

    system_prompt = """Extract farm size from the farmer's message.
    Convert to hectares. Examples:
    - "5 hectares" → 5.0
    - "2 acres" → 0.8 (convert acres to hectares)
    - "half hectare" → 0.5
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]

    extraction = await self.openai_service.structured_output(
        messages=messages,
        response_model=FarmSizeExtraction
    )

    return extraction.farm_size
```

**That's it! No changes to service logic or integration code.**

---

## Future Fields as JSON Storage

For scalability and flexibility, **future profile fields** (beyond the core 4) will be stored in a single JSON column rather than adding individual database columns for each new field. This approach provides ultimate extensibility without requiring database migrations.

### Design Rationale

**Why JSON storage for future fields?**

✅ **No Schema Migrations**: Add unlimited fields without altering database schema  
✅ **Rapid Iteration**: Test new fields in production without deployment overhead  
✅ **Field Versioning**: Easy to deprecate/rename fields without breaking existing data  
✅ **Flexible Structure**: Support nested objects, arrays, and complex data types  
✅ **Query Performance**: PostgreSQL JSONB type provides efficient indexing and querying  

**Core Fields (Direct Columns):**
- `administration` (relationship table)
- `crop_type` (String)
- `gender` (Enum)
- `age_group` (Enum)

**Extended Fields (JSON Column):**
- `farm_size` (Float)
- `years_experience` (Integer)
- `farming_practices` (Array of strings)
- `irrigation_method` (String)
- `livestock_count` (Object with animal types)
- `contact_preferences` (Object with channels)
- ... any future fields

### Database Schema Addition

Add a single JSON column to store all extended profile fields:

```python
# backend/models/customer.py

class Customer(Base):
    # ... existing columns ...
    
    # Extended profile fields stored as JSON
    profile_data = Column(JSON, nullable=True)
    # Structure: {
    #   "farm_size": 5.5,
    #   "years_experience": 10,
    #   "farming_practices": ["organic", "drip_irrigation"],
    #   "livestock_count": {"cattle": 3, "goats": 12},
    #   "irrigation_method": "drip",
    #   "last_updated": "2025-12-01T10:30:00Z"
    # }
```

**Migration to add profile_data column:**

```python
# backend/alembic/versions/YYYYMMDD_HHMMSS_add_profile_data_json.py

def upgrade():
    op.add_column(
        'customers',
        sa.Column('profile_data', sa.JSON(), nullable=True)
    )
    
    # Optional: Create GIN index for efficient JSON queries
    op.execute("""
        CREATE INDEX idx_customers_profile_data_gin 
        ON customers USING GIN (profile_data jsonb_path_ops)
    """)

def downgrade():
    op.drop_index('idx_customers_profile_data_gin', table_name='customers')
    op.drop_column('customers', 'profile_data')
```

### Configuration for JSON Fields

```python
# backend/config/onboarding_fields.py

ONBOARDING_FIELDS.append(
    OnboardingFieldConfig(
        field_name="farm_size",
        db_field="profile_data.farm_size",  # JSON path notation
        required=False,
        priority=5,
        initial_question="How large is your farm in hectares?",
        extraction_method="extract_farm_size",
        matching_method=None,
        max_attempts=2,
        field_type="direct",
        success_message_template="Thank you! I've noted your farm is {farm_size} hectares.",
    )
)

ONBOARDING_FIELDS.append(
    OnboardingFieldConfig(
        field_name="farming_practices",
        db_field="profile_data.farming_practices",  # Array in JSON
        required=False,
        priority=6,
        initial_question=(
            "What farming practices do you use? "
            "For example: organic, drip irrigation, crop rotation, etc."
        ),
        extraction_method="extract_farming_practices",
        matching_method=None,
        max_attempts=2,
        field_type="direct",
        success_message_template="Great! I've noted your farming practices.",
    )
)
```

### Service Logic for JSON Fields

Update `_save_field_value()` to handle JSON paths:

```python
# backend/services/onboarding_service.py

def _save_field_value(
    self,
    customer: Customer,
    value: Any,
    field_config: OnboardingFieldConfig
) -> OnboardingResponse:
    """
    Save field value to database and move to next field.
    
    Handles both direct columns and JSON paths.
    """
    field_name = field_config.field_name

    try:
        # Special case: administration (relationship table)
        if field_name == "administration":
            self._save_administration(customer, value)
            success_msg = field_config.success_message_template.format(
                location_name=value.path
            )

        # Check if db_field uses JSON path notation
        elif field_config.db_field and "." in field_config.db_field:
            # JSON field: "profile_data.farm_size"
            json_column, json_key = field_config.db_field.split(".", 1)
            
            # Get or initialize JSON object
            profile_data = getattr(customer, json_column) or {}
            
            # Support nested paths: "profile_data.livestock.cattle"
            keys = json_key.split(".")
            current = profile_data
            
            # Navigate to parent
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # Set the value
            current[keys[-1]] = value
            
            # Save back to column
            setattr(customer, json_column, profile_data)
            
            # Mark as modified (important for SQLAlchemy JSON tracking)
            flag_modified(customer, json_column)
            
            success_msg = field_config.success_message_template or "Thank you!"

        # Standard case: direct column
        elif field_config.db_field:
            setattr(customer, field_config.db_field, value)
            success_msg = field_config.success_message_template or "Thank you!"

        else:
            logger.error(f"No save logic for field: {field_name}")
            success_msg = "Thank you!"

        # Clear field-specific state
        self._clear_field_state(customer, field_name)

        # Commit changes
        self.db.commit()

        logger.info(
            f"Saved {field_name} for customer {customer.id}: {value}"
        )

        # Check if there are more fields
        next_field = self._get_next_incomplete_field(customer)

        if next_field:
            return self._ask_initial_question(customer, next_field)
        else:
            return self._complete_onboarding(customer)

    except Exception as e:
        logger.error(f"Failed to save {field_name}: {e}", exc_info=True)
        self.db.rollback()

        return OnboardingResponse(
            status="in_progress",
            message="Sorry, I had trouble saving that information. Please try again."
        )
```

**Important:** Import `flag_modified` from SQLAlchemy:

```python
from sqlalchemy.orm.attributes import flag_modified
```

### Checking Field Completion for JSON Fields

Update `_is_field_complete()` to handle JSON paths:

```python
def _is_field_complete(
    self,
    customer: Customer,
    field_config: OnboardingFieldConfig
) -> bool:
    """
    Check if a specific field is already filled.
    
    Handles both direct columns and JSON paths.
    """
    field_name = field_config.field_name

    # Special case: administration uses relationship table
    if field_name == "administration":
        return self.db.query(CustomerAdministrative).filter_by(
            customer_id=customer.id
        ).count() > 0

    # Check if db_field uses JSON path notation
    if field_config.db_field and "." in field_config.db_field:
        # JSON field: "profile_data.farm_size"
        json_column, json_key = field_config.db_field.split(".", 1)
        
        profile_data = getattr(customer, json_column)
        if not profile_data:
            return False
        
        # Navigate nested path
        keys = json_key.split(".")
        current = profile_data
        
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        
        # Check if value exists and is not None/empty
        return current is not None and current != ""

    # Standard case: check Customer model field
    if field_config.db_field:
        field_value = getattr(customer, field_config.db_field)
        return field_value is not None

    return False
```

### Querying JSON Fields

PostgreSQL JSONB provides powerful query capabilities:

```python
# Query customers with specific farm size range
customers = db.query(Customer).filter(
    Customer.profile_data['farm_size'].astext.cast(Float) >= 5.0,
    Customer.profile_data['farm_size'].astext.cast(Float) <= 10.0
).all()

# Query customers using organic farming
customers = db.query(Customer).filter(
    Customer.profile_data['farming_practices'].astext.contains('organic')
).all()

# Query customers with livestock
customers = db.query(Customer).filter(
    Customer.profile_data.has_key('livestock_count')
).all()

# Complex nested queries
customers = db.query(Customer).filter(
    Customer.profile_data['livestock_count']['cattle'].astext.cast(Integer) > 5
).all()
```

### Example: Complete JSON Field Implementation

**Add "Years of Experience" field:**

1. **Configuration** (no migration needed):

```python
# backend/config/onboarding_fields.py

ONBOARDING_FIELDS.append(
    OnboardingFieldConfig(
        field_name="years_experience",
        db_field="profile_data.years_experience",
        required=False,
        priority=7,
        initial_question="How many years have you been farming?",
        extraction_method="extract_years_experience",
        matching_method=None,
        max_attempts=2,
        field_type="direct",
        success_message_template="Thank you! I've noted you have {years_experience} years of experience.",
    )
)
```

2. **Extraction method**:

```python
# backend/services/onboarding_service.py

async def extract_years_experience(self, message: str) -> int:
    """Extract years of farming experience from message"""
    class ExperienceExtraction(BaseModel):
        years_experience: int = Field(
            description="Number of years farming (whole number)"
        )

    system_prompt = """Extract farming experience in years.
    Examples:
    - "5 years" → 5
    - "been farming for ten years" → 10
    - "I started in 2015" → calculate years from 2015 to now
    - "20 months" → 2 (round to nearest year)
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]

    extraction = await self.openai_service.structured_output(
        messages=messages,
        response_model=ExperienceExtraction
    )

    return extraction.years_experience
```

3. **That's it!** The generic service handles the rest automatically.

### Benefits of JSON Storage Approach

| Aspect | Traditional Columns | JSON Storage |
|--------|---------------------|--------------|
| **Adding Fields** | Migration required | Config update only |
| **Field Types** | Limited to SQL types | Any JSON-serializable type |
| **Nested Data** | Multiple tables/columns | Single JSON object |
| **Deprecation** | Leave orphan columns | Simply stop collecting |
| **Versioning** | Complex migrations | Store version in JSON |
| **Testing** | Deploy to test changes | Test in production safely |
| **Deployment** | Downtime for migration | Zero downtime |

### Best Practices for JSON Fields

**DO:**
- ✅ Use JSON for optional, experimental, or frequently-changing fields
- ✅ Index commonly-queried JSON fields using GIN indexes
- ✅ Validate JSON structure at application level
- ✅ Store metadata (last_updated, version) in JSON object
- ✅ Use consistent naming conventions (snake_case)

**DON'T:**
- ❌ Don't use JSON for core business logic fields (use direct columns)
- ❌ Don't store large binary data in JSON (use separate storage)
- ❌ Don't create deeply nested structures (max 2-3 levels)
- ❌ Don't forget to call `flag_modified()` after updating JSON
- ❌ Don't use JSON if you need foreign key constraints

### Migration Path: JSON → Column

If a JSON field becomes critical, migrate it to a proper column:

```python
# backend/alembic/versions/YYYYMMDD_HHMMSS_promote_farm_size_to_column.py

def upgrade():
    # Add new column
    op.add_column(
        'customers',
        sa.Column('farm_size', sa.Float(), nullable=True)
    )
    
    # Migrate data from JSON
    op.execute("""
        UPDATE customers
        SET farm_size = (profile_data->>'farm_size')::float
        WHERE profile_data ? 'farm_size'
    """)
    
    # Optional: Remove from JSON
    op.execute("""
        UPDATE customers
        SET profile_data = profile_data - 'farm_size'
        WHERE profile_data ? 'farm_size'
    """)

def downgrade():
    # Move data back to JSON
    op.execute("""
        UPDATE customers
        SET profile_data = jsonb_set(
            COALESCE(profile_data, '{}'::jsonb),
            '{farm_size}',
            to_jsonb(farm_size)
        )
        WHERE farm_size IS NOT NULL
    """)
    
    op.drop_column('customers', 'farm_size')
```

**That's it! No changes to service logic or integration code.**

---

## Benefits Summary

| Aspect | Current System | Generic System |
|--------|---------------|----------------|
| **Scalability** | ❌ New service per field | ✅ Config-driven, no code changes |
| **Database Schema** | ❌ New columns per field | ✅ 4 columns handle unlimited fields |
| **Code Duplication** | ❌ Duplicate logic everywhere | ✅ Single generic handler |
| **State Management** | ❌ Multiple status fields | ✅ Single state machine |
| **Testing** | ❌ Test each service separately | ✅ Test once, works for all fields |
| **Maintenance** | ❌ Update multiple services | ✅ Update one service |
| **Priority Control** | ❌ Hard-coded in routing | ✅ Configured in one place |
| **Extensibility** | ❌ Requires schema migration | ✅ Add to config, optional migration |

---

## Migration Risks & Mitigation

### Risk 1: Data Loss During Migration
**Mitigation**:
- Backup database before migration
- Test migration on development first
- Use PostgreSQL JSON functions for safe conversion
- Verify data integrity after migration

### Risk 2: Breaking Existing Onboarding
**Mitigation**:
- Keep existing `extract_location` and `match_administrative` methods unchanged
- Maintain same OnboardingResponse interface
- Test thoroughly with real WhatsApp messages

### Risk 3: Performance Degradation
**Mitigation**:
- JSON operations are fast in PostgreSQL
- Index JSON fields if needed
- Monitor query performance
- Use LRU cache on service factory

### Rollback Plan

If issues arise:

```bash
# Rollback database
./dc.sh exec backend alembic downgrade -1

# Revert code
git revert <commit-hash>

# Redeploy
./dc.sh restart backend
```

---

## Success Criteria

✅ All existing administration onboarding tests pass
✅ New crop type collection works end-to-end
✅ Gender and age group collection works
✅ Priority order is enforced (administration → crop → gender → age)
✅ Ambiguous matches handled for all fuzzy_match fields
✅ Max attempts handled gracefully
✅ 90%+ test coverage on onboarding service
✅ No regression in existing message flow
✅ Database migration runs successfully
✅ Performance metrics unchanged (< 2s response time)

---

## Timeline Estimate

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1 | Database schema + migration | 2-3 hours |
| Phase 2 | Configuration file | 1 hour |
| Phase 3 | Service refactoring | 4-6 hours |
| Phase 4 | Integration updates | 1-2 hours |
| Phase 5 | Testing | 4-5 hours |
| Phase 6 | Manual testing | 2-3 hours |
| Phase 7 | Documentation | 1-2 hours |
| **Total** | | **15-22 hours** |

---

## Conclusion

The generic onboarding system provides a **scalable, maintainable solution** for collecting multiple farmer profile fields. By moving from hard-coded field-specific services to a configuration-driven generic service, we enable:

- **Easy addition of new fields** (just update config)
- **Consistent user experience** across all fields
- **Single source of truth** for onboarding logic
- **Reduced code duplication**
- **Improved testability**

This architecture positions AgriConnect for future growth as we add more profile fields and onboarding requirements.

**Next Steps**: Begin implementation with Phase 1 (Database Schema & Migration).
