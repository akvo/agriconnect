# Implementation Plan: AI Onboarding Workflow for Farmers

**Date:** 2025-11-06
**Author:** AgriConnect Team
**Status:** Planning
**Objective:** Implement AI-driven onboarding to collect administrative location data (province, district, ward) from farmers before allowing regular chat interactions

---

## 📊 Overview

### Purpose

When a farmer sends their first message and their administrative data (province, district, ward) is empty, the system automatically starts an AI onboarding workflow. The backend replies by asking for location information before processing any other questions with the external AI service. This ensures proper farmer registration and enables ward-based ticket routing to extension officers.

### Multi-Stage Onboarding (This is Stage 1)

This document describes **Stage 1: Location Data Collection**, which is the first and most critical stage of the onboarding workflow.

**Why Location is Critical:**
- **Extension Officer Assignment** - Farmers are routed to EOs based on their ward
- **Ticket Creation** - Escalated tickets are assigned to the correct administrative area
- **Mandatory for System Operation** - Without location, farmers cannot be connected to the right advisors

**Future Onboarding Stages** (not covered in this document):
- **Stage 2:** Farmer Profile (crop type, age group, gender, farm size)
- **Stage 3:** Preferences (language, notification settings)

**Important:** We ask for **one category at a time**, not everything at once. The onboarding service pattern designed here can be reused for future stages with minimal changes.

### Key Features

1. **Automatic detection** - System detects when customer lacks administrative data
2. **OpenAI-driven conversation** - Uses direct OpenAI integration for location extraction
3. **Hierarchical fuzzy matching** - Matches province/district/ward with typo tolerance
4. **Ambiguity detection** - Detects duplicate ward names across districts
5. **Interactive selection** - Shows numbered options when multiple matches found
6. **Smart retry logic** - Asks up to 3 times for clarification
7. **Graceful failure** - Continues conversation normally after 3 failed attempts
8. **Seamless transition** - Switches to external AI service after successful onboarding

---

## 🎯 User Stories

### Story 1: Successful Onboarding (Unique Match)
```
Farmer: Hello, I need help with my maize crop
Bot: Welcome to AgriConnect! To connect you with the right agricultural advisor,
     could you tell me where you're located? Please share your ward, district,
     and province/region.
Farmer: I'm in Kivulini ward, Mwanga district, Kilimanjaro
Bot: [extracts: Kilimanjaro > Mwanga > Kivulini]
     [matches uniquely: Tanzania > Kilimanjaro > Mwanga > Kivulini]
Bot: Thank you! You're registered in Kivulini ward, Mwanga district, Kilimanjaro. ✅
     Now, how can I help you with your maize crop?
[continues with external AI service]
```

### Story 2: Ambiguous Match (Selection Required)
```
Farmer: Hello
Bot: Welcome to AgriConnect! To connect you with the right agricultural advisor,
     could you tell me where you're located? Please share your ward, district,
     and province/region.
Farmer: Kivulini ward, Kilimanjaro
Bot: [extracts: Kivulini, Kilimanjaro, no district]
     [finds 2 matches with similar scores]
Bot: I found multiple areas named 'Kivulini' in Kilimanjaro:

     1. Mwanga district, Kilimanjaro
     2. Same district, Kilimanjaro

     Please reply with the number that matches your location.
Farmer: 1
Bot: [saves: Tanzania > Kilimanjaro > Mwanga > Kivulini]
Bot: Perfect! You're registered in Kivulini ward, Mwanga district, Kilimanjaro. ✅
     How can I help you today?
```

### Story 3: Typo Tolerance
```
Farmer: Hello
Bot: Welcome to AgriConnect!...
Farmer: Kivulni ward, Mwaga district, Kilimanjro
Bot: [fuzzy matches despite typos: Kivulini, Mwanga, Kilimanjaro]
     [unique match found with score 89]
Bot: Thank you! You're registered in Kivulini ward, Mwanga district, Kilimanjaro. ✅
     How can I help you today?
```

### Story 4: Failed Onboarding (After 3 Attempts)
```
Farmer: Hello
Bot: Welcome to AgriConnect!...
Farmer: Tanzania
Bot: Could you be more specific? Please tell me your ward and district.
Farmer: Near Moshi
Bot: I understand you're near Moshi. Could you tell me the specific ward and district name?
Farmer: Not sure
Bot: [marks onboarding as failed]
Bot: No problem! Let me help you anyway. What would you like to know?
[continues with external AI service, but without location data]
```

---

## 📐 Architecture Design

### Database Schema Changes

#### 1. Add Onboarding Fields to `customers` Table

```python
# backend/models/customer.py

class OnboardingStatus(enum.Enum):
    NOT_STARTED = "not_started"     # No onboarding needed or not started
    IN_PROGRESS = "in_progress"     # Currently collecting location data
    COMPLETED = "completed"         # Successfully collected location data
    FAILED = "failed"              # Failed after max attempts

class Customer(Base):
    __tablename__ = "customers"

    # ... existing fields ...

    # Onboarding tracking
    onboarding_status = Column(
        Enum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED,
        nullable=False
    )
    onboarding_attempts = Column(Integer, default=0, nullable=False)
    onboarding_started_at = Column(DateTime(timezone=True), nullable=True)
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)

    # Store candidate ward IDs when multiple matches found (JSON array)
    onboarding_candidates = Column(Text, nullable=True)  # e.g., "[123, 456, 789]"
```

**Migrations:**
- `alembic/versions/XXXX_rebuild_administrative_paths.py` - Fix existing paths (CRITICAL)
- `alembic/versions/XXXX_add_onboarding_to_customers.py` - Add onboarding fields

#### 2. Fix Administrative Path Format

**Problem:** Current seeder stores paths using codes (e.g., `KEN.NBI.NRB-C.NRB-C-1`)
**Solution:** Update to human-readable names (e.g., `Kenya > Nairobi Region > Central District > Westlands Ward`)

This is **CRITICAL** for hierarchical fuzzy matching to work!

### Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WhatsApp Router                          │
│             (receives farmer message)                       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │ Check customer│
         │ admin data?   │
         └───────┬───────┘
                 │
      ┌──────────┴──────────┐
      │                     │
  YES │                     │ NO
      ▼                     ▼
┌─────────────┐    ┌──────────────────────────┐
│ External AI │    │ Onboarding Service       │
│ Service     │    │ (OpenAI)                 │
│ (Normal     │    │ - Extract location       │
│  chat)      │    │ - Hierarchical fuzzy     │
└─────────────┘    │   matching (ward path)   │
                   │ - Detect ambiguity       │
                   │ - Show numbered options  │
                   │ - Save to DB             │
                   │ - Retry (max 3)          │
                   └──────────────────────────┘
```

### Hierarchical Matching Flow

```
Farmer says: "Kivulini ward, Mwanga district, Kilimanjaro"
    ↓
OpenAI extracts:
  - ward: "Kivulini"
  - district: "Mwanga"
  - province: "Kilimanjaro"
    ↓
Query all wards from database
    ↓
For each ward, calculate score based on path:
    ↓
Ward 1: "Tanzania > Kilimanjaro > Mwanga > Kivulini"
  - Ward match: 100 (exact)
  - District match: 100 (exact)
  - Province match: 100 (exact)
  - Weighted score: (100×3 + 100×2 + 100×1) / 6 = 100 ✅
    ↓
Ward 2: "Tanzania > Kilimanjaro > Same > Kivulini"
  - Ward match: 100 (exact)
  - District match: 0 (Mwanga ≠ Same)
  - Province match: 100 (exact)
  - Weighted score: (100×3 + 0×2 + 100×1) / 6 = 66 ❌
    ↓
Ward 3: "Tanzania > Arusha > Meru > Kivulini"
  - Ward match: 100 (exact)
  - District match: 0 (Mwanga ≠ Meru)
  - Province match: 0 (Kilimanjaro ≠ Arusha)
  - Weighted score: (100×3 + 0×2 + 0×1) / 6 = 50 ❌
    ↓
Best match: Ward 1 (score: 100) - UNIQUE ✅
    ↓
Save to customer_administrative table
```

---

## 🔧 Implementation Plan

### Phase 0: Fix Administrative Path Format (CRITICAL - DO THIS FIRST)

**Why:** Onboarding relies on human-readable paths for matching. Current seeder uses code-based paths which won't work with fuzzy matching.

#### Step 0.1: Update Administrative Seeder

**File:** `backend/seeder/administrative.py`

**Changes:**

```python
# REPLACE build_ltree_path function (line 15-19):
def build_human_readable_path(parent_path: str, name: str) -> str:
    """
    Build human-readable path from parent path and name.

    Format: "Country > Region > District > Ward"
    Example: "Kenya > Nairobi Region > Central District > Westlands Ward"

    Args:
        parent_path: Parent's path (or empty for root)
        name: Current administrative area name

    Returns:
        Full hierarchical path with '>' separator
    """
    if parent_path:
        return f"{parent_path} > {name}"
    return name


# UPDATE line 159-161 (existing record update):
if existing:
    if existing.name != name or existing.parent_id != (
        parent.id if parent else None
    ):
        existing.name = name
        existing.parent_id = parent.id if parent else None
        existing.path = build_human_readable_path(
            parent.path if parent else "", name  # Changed: use NAME not code
        )
        stats["updated"] += 1
    else:
        stats["skipped"] += 1


# UPDATE line 167 (new record creation):
else:
    # Create new
    path = build_human_readable_path(parent.path if parent else "", name)  # Changed: use NAME
    admin = Administrative(
        code=code,
        name=name,
        level_id=level.id,
        parent_id=parent.id if parent else None,
        path=path,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    stats["created"] += 1
```

**Why this matters:**
- **Before:** Path = `KEN.NBI.NRB-C.NRB-C-1` (codes, unusable for matching)
- **After:** Path = `Kenya > Nairobi Region > Central District > Westlands Ward` (names, perfect for fuzzy matching)

#### Step 0.2: Create Migration to Fix Existing Paths

**File:** `backend/alembic/versions/XXXX_rebuild_administrative_paths.py`

```python
"""Rebuild administrative paths with human-readable names

Revision ID: rebuild_administrative_paths
Revises: <previous_revision>
Create Date: 2025-11-06

This migration rebuilds all administrative paths to use human-readable names
instead of codes. Required for AI onboarding hierarchical fuzzy matching.

Before: "KEN.NBI.NRB-C.NRB-C-1"
After:  "Kenya > Nairobi Region > Central District > Westlands Ward"
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'rebuild_administrative_paths'
down_revision = '<previous_revision_id>'
branch_labels = None
depends_on = None


def upgrade():
    """Rebuild all administrative paths using names instead of codes"""

    connection = op.get_bind()

    print("[Migration] Rebuilding administrative paths with human-readable names...")

    # Recursive query to rebuild paths
    connection.execute(text("""
        -- Create temporary function to build path from names
        CREATE OR REPLACE FUNCTION rebuild_admin_path(admin_id INTEGER)
        RETURNS TEXT AS $$
        DECLARE
            current_name TEXT;
            parent_path TEXT;
            parent_id_val INTEGER;
        BEGIN
            -- Get current admin's name and parent_id
            SELECT name, parent_id INTO current_name, parent_id_val
            FROM administrative
            WHERE id = admin_id;

            -- If no parent, return just the name (root level)
            IF parent_id_val IS NULL THEN
                RETURN current_name;
            END IF;

            -- Recursively get parent path
            parent_path := rebuild_admin_path(parent_id_val);

            -- Return concatenated path with ' > ' separator
            RETURN parent_path || ' > ' || current_name;
        END;
        $$ LANGUAGE plpgsql;

        -- Update all paths in administrative table
        UPDATE administrative
        SET path = rebuild_admin_path(id);

        -- Drop temporary function
        DROP FUNCTION rebuild_admin_path(INTEGER);
    """))

    # Get count for verification
    result = connection.execute(text("SELECT COUNT(*) FROM administrative"))
    count = result.scalar()

    print(f"[Migration] ✓ Rebuilt {count} administrative paths")
    print("[Migration] Example paths:")

    # Show sample paths
    samples = connection.execute(text("""
        SELECT name, path
        FROM administrative
        JOIN administrative_levels ON administrative.level_id = administrative_levels.id
        WHERE administrative_levels.name = 'Ward'
        LIMIT 3
    """))

    for row in samples:
        print(f"  - {row[0]}: {row[1]}")


def downgrade():
    """Restore code-based ltree paths (for rollback)"""

    connection = op.get_bind()

    print("[Migration] Restoring code-based paths...")

    # Rebuild using codes with '.' separator (reverse operation)
    connection.execute(text("""
        CREATE OR REPLACE FUNCTION rebuild_admin_code_path(admin_id INTEGER)
        RETURNS TEXT AS $$
        DECLARE
            current_code TEXT;
            parent_path TEXT;
            parent_id_val INTEGER;
        BEGIN
            SELECT code, parent_id INTO current_code, parent_id_val
            FROM administrative
            WHERE id = admin_id;

            IF parent_id_val IS NULL THEN
                RETURN current_code;
            END IF;

            parent_path := rebuild_admin_code_path(parent_id_val);
            RETURN parent_path || '.' || current_code;
        END;
        $$ LANGUAGE plpgsql;

        UPDATE administrative
        SET path = rebuild_admin_code_path(id);

        DROP FUNCTION rebuild_admin_code_path(INTEGER);
    """))

    print("[Migration] ✓ Restored code-based paths")
```

**When to run:**
- **For existing databases:** Run this migration to fix paths immediately
- **For new databases:** Seeder automatically creates correct paths

---

### Phase 1: Database Schema Updates

#### Step 1.1: Update Customer Model

**File:** `backend/models/customer.py`

```python
import enum
from sqlalchemy import Column, DateTime, Enum, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class OnboardingStatus(enum.Enum):
    """Customer onboarding status for location data collection"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Customer(Base):
    __tablename__ = "customers"

    # ... existing fields ...

    # Onboarding tracking
    onboarding_status = Column(
        Enum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED,
        nullable=False
    )
    onboarding_attempts = Column(Integer, default=0, nullable=False)
    onboarding_started_at = Column(DateTime(timezone=True), nullable=True)
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)
    onboarding_candidates = Column(Text, nullable=True)

    def needs_onboarding(self) -> bool:
        """
        Check if customer needs onboarding.

        Returns True if:
        - Customer has no administrative data (no ward assigned)
        - Onboarding is NOT_STARTED or IN_PROGRESS
        - Onboarding has not FAILED
        """
        has_location = bool(self.customer_administrative)

        if has_location:
            return False

        return self.onboarding_status in (
            OnboardingStatus.NOT_STARTED,
            OnboardingStatus.IN_PROGRESS
        )
```

#### Step 1.2: Create Alembic Migration for Customer Onboarding

**File:** `backend/alembic/versions/XXXX_add_onboarding_to_customers.py`

```python
"""Add onboarding fields to customers table

Revision ID: add_onboarding_to_customers
Revises: rebuild_administrative_paths
Create Date: 2025-11-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_onboarding_to_customers'
down_revision = 'rebuild_administrative_paths'  # Run AFTER path rebuild
branch_labels = None
depends_on = None


def upgrade():
    """Add onboarding tracking fields to customers table"""
    # Create enum type
    onboarding_status_enum = sa.Enum(
        'not_started', 'in_progress', 'completed', 'failed',
        name='onboardingstatus'
    )
    onboarding_status_enum.create(op.get_bind(), checkfirst=True)

    # Add columns
    op.add_column(
        'customers',
        sa.Column(
            'onboarding_status',
            sa.Enum('not_started', 'in_progress', 'completed', 'failed',
                    name='onboardingstatus'),
            nullable=False,
            server_default='not_started'
        )
    )
    op.add_column(
        'customers',
        sa.Column('onboarding_attempts', sa.Integer(), nullable=False,
                  server_default='0')
    )
    op.add_column(
        'customers',
        sa.Column('onboarding_started_at', sa.DateTime(timezone=True),
                  nullable=True)
    )
    op.add_column(
        'customers',
        sa.Column('onboarding_completed_at', sa.DateTime(timezone=True),
                  nullable=True)
    )
    op.add_column(
        'customers',
        sa.Column('onboarding_candidates', sa.Text(), nullable=True)
    )

    # Set COMPLETED status for customers who already have administrative data
    op.execute("""
        UPDATE customers c
        SET onboarding_status = 'completed',
            onboarding_completed_at = c.created_at
        WHERE EXISTS (
            SELECT 1 FROM customer_administrative ca
            WHERE ca.customer_id = c.id
        )
    """)


def downgrade():
    """Remove onboarding tracking fields"""
    op.drop_column('customers', 'onboarding_candidates')
    op.drop_column('customers', 'onboarding_completed_at')
    op.drop_column('customers', 'onboarding_started_at')
    op.drop_column('customers', 'onboarding_attempts')
    op.drop_column('customers', 'onboarding_status')

    # Drop enum type
    sa.Enum(name='onboardingstatus').drop(op.get_bind(), checkfirst=True)
```

---

### Phase 2: Dependencies

#### Step 2.1: Update requirements.txt

**File:** `backend/requirements.txt`

```txt
# Add fuzzy string matching library
rapidfuzz>=3.0.0
```

**Note:** `rapidfuzz` is faster and more efficient than `fuzzywuzzy`

---

### Phase 3: Onboarding Service Implementation

#### Step 3.1: Create Onboarding Schemas

**File:** `backend/schemas/onboarding_schemas.py`

```python
"""
Schemas for AI onboarding workflow.
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field


class LocationData(BaseModel):
    """Structured location data extracted from farmer response"""
    province: Optional[str] = Field(None, description="Province/Region name")
    district: Optional[str] = Field(None, description="District name")
    ward: Optional[str] = Field(None, description="Ward name")
    confidence: Literal["high", "medium", "low"] = Field(
        "low",
        description="Confidence level of extraction"
    )
    needs_clarification: bool = Field(
        True,
        description="Whether more information is needed"
    )
    clarification_question: Optional[str] = Field(
        None,
        description="Follow-up question to ask farmer"
    )


class OnboardingResponse(BaseModel):
    """Response from onboarding service"""
    message: str  # Message to send to farmer
    completed: bool  # Whether onboarding is complete
    location_data: Optional[LocationData] = None
    should_retry: bool  # Whether to continue onboarding attempts
```

#### Step 3.2: Create Onboarding Service

**File:** `backend/services/onboarding_service.py`

This file contains the full implementation with all methods. Key components:

**Main Methods:**
- `process_onboarding_message()` - Entry point for processing farmer messages
- `_extract_location()` - Uses OpenAI structured output to extract location data
- `_find_administrative_area()` - Hierarchical fuzzy matching on administrative paths
- `_calculate_hierarchical_score()` - Weighted scoring (ward×3, district×2, province×1)
- `_ask_to_select_from_options()` - Shows numbered options when ambiguous
- `_parse_selection()` - Parses farmer's number selection (1-5)
- `_handle_selection()` - Retrieves selected ward from stored candidates
- `_save_location()` - Saves ward to customer_administrative table
- `_complete_onboarding()` - Success flow with confirmation message
- `_fail_onboarding()` - Graceful failure after max attempts

**Fuzzy Matching Logic:**
```python
def _calculate_hierarchical_score(ward, location_data):
    # Parse path: "Tanzania > Kilimanjaro > Mwanga > Kivulini"
    path_parts = ward.path.split(">")

    # Extract levels
    actual_province = path_parts[-3]
    actual_district = path_parts[-2]
    actual_ward = path_parts[-1]

    # Calculate fuzzy match scores
    ward_score = fuzz.ratio(location_data.ward, actual_ward)
    district_score = fuzz.ratio(location_data.district, actual_district)
    province_score = fuzz.ratio(location_data.province, actual_province)

    # Weighted average (ward is most important)
    weighted_score = (ward_score×3 + district_score×2 + province_score×1) / 6

    return weighted_score
```

---

### Phase 4: WhatsApp Router Integration

#### Step 4.1: Update WhatsApp Router

**File:** `backend/routers/whatsapp.py`

**Add import at top:**
```python
from services.onboarding_service import get_onboarding_service
```

**Add onboarding check BEFORE external AI service:**

```python
async def process_incoming_message(...):
    # ... existing code to get/create customer ...

    # CHECK FOR ONBOARDING FIRST
    onboarding_service = get_onboarding_service(db)

    if onboarding_service.should_start_onboarding(customer):
        logger.info(
            f"[Onboarding] Customer {customer.id} needs onboarding"
        )

        # Process with onboarding service
        onboarding_response = await onboarding_service.process_onboarding_message(
            customer=customer,
            message_text=message_body
        )

        # Send onboarding message back to farmer
        await send_whatsapp_message(
            to_number=customer.phone_number,
            message=onboarding_response.message
        )

        # If onboarding completed, continue to external AI for original question
        if onboarding_response.completed and not onboarding_response.should_retry:
            logger.info(
                f"[Onboarding] Completed for customer {customer.id}, "
                f"continuing to external AI"
            )
            # Fall through to external AI processing below
        else:
            # Still in onboarding, return early
            return

    # EXISTING CODE: Process with external AI service
    ai_service = get_external_ai_service(db)
    # ... rest of existing logic ...
```

---

### Phase 5: Configuration Updates

#### Step 5.1: Update config.template.json

**File:** `backend/config.template.json`

```json
{
  "openai": {
    "features": {
      "onboarding": {
        "enabled": true,
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 300,
        "max_attempts": 3,
        "min_match_score": 75,
        "ambiguity_threshold": 15,
        "system_prompt": "You are a location data extraction assistant for AgriConnect in Tanzania. Extract province/region, district, and ward from farmer messages.",
        "description": "AI-driven onboarding to collect farmer location data with hierarchical fuzzy matching"
      }
    }
  }
}
```

#### Step 5.2: Update config.py

**File:** `backend/config.py`

```python
# Add onboarding configuration
openai_onboarding_enabled: bool = (
    _config.get("openai", {})
    .get("features", {})
    .get("onboarding", {})
    .get("enabled", True)
)
openai_onboarding_max_attempts: int = (
    _config.get("openai", {})
    .get("features", {})
    .get("onboarding", {})
    .get("max_attempts", 3)
)
openai_onboarding_min_match_score: int = (
    _config.get("openai", {})
    .get("features", {})
    .get("onboarding", {})
    .get("min_match_score", 75)
)
```

---

### Phase 6: Testing

#### Step 6.1: Unit Tests

**File:** `backend/tests/services/test_onboarding_service.py`

Test coverage:
- `test_should_start_onboarding()` - Detection logic
- `test_start_onboarding()` - Initial welcome message
- `test_hierarchical_scoring_exact_match()` - Perfect match scoring
- `test_hierarchical_scoring_partial_match()` - Missing district/province
- `test_hierarchical_scoring_typos()` - Fuzzy matching tolerance
- `test_find_administrative_area_unique()` - Single clear match
- `test_find_administrative_area_ambiguous()` - Multiple matches
- `test_parse_selection()` - Number parsing (1, "first", "number 2", etc.)
- `test_handle_selection()` - Candidate retrieval
- `test_onboarding_max_attempts()` - Graceful failure

#### Step 6.2: Integration Tests

**File:** `backend/tests/test_whatsapp_onboarding.py`

Test scenarios:
- New farmer triggers onboarding
- Farmer provides complete location (success)
- Farmer provides partial location (ambiguous selection)
- Farmer selects from numbered options
- Farmer fails after 3 attempts
- Existing farmer with location skips onboarding

---

## ✅ Implementation Checklist

### Phase 0: Administrative Path Fix (CRITICAL - DO THIS FIRST)
- [ ] Update `seeder/administrative.py`:
  - [ ] Replace `build_ltree_path()` with `build_human_readable_path()`
  - [ ] Update line 159-161 to use `name` instead of `code`
  - [ ] Update line 167 to use `name` instead of `code`
- [ ] Create migration `rebuild_administrative_paths.py`
- [ ] Run migration: `./dc.sh exec backend alembic upgrade head`
- [ ] Verify paths are human-readable:
  ```bash
  ./dc.sh exec backend bash -c "cd /app && python3 -c \"
  from database import SessionLocal
  from models.administrative import Administrative, AdministrativeLevel
  db = SessionLocal()
  wards = db.query(Administrative).join(Administrative.level).filter(AdministrativeLevel.name=='Ward').limit(3).all()
  for w in wards:
      print(f'{w.name}: {w.path}')
  db.close()
  \""
  ```
- [ ] Expected: `Westlands Ward: Kenya > Nairobi Region > Central District > Westlands Ward`

### Phase 1: Database
- [ ] Add `OnboardingStatus` enum to `customer.py`
- [ ] Add onboarding fields to `Customer` model
- [ ] Add `onboarding_candidates` column
- [ ] Add `needs_onboarding()` method
- [ ] Create migration `add_onboarding_to_customers.py`
- [ ] Run migration: `./dc.sh exec backend alembic upgrade head`
- [ ] Verify existing customers have `completed` status

### Phase 2: Dependencies
- [ ] Add `rapidfuzz>=3.0.0` to `requirements.txt`
- [ ] Install: `./dc.sh exec backend pip install -r requirements.txt`

### Phase 3: Services
- [ ] Create `schemas/onboarding_schemas.py`
- [ ] Create `services/onboarding_service.py`
- [ ] Implement OpenAI location extraction
- [ ] Implement hierarchical fuzzy matching
- [ ] Implement ambiguity detection
- [ ] Implement selection handling
- [ ] Implement retry logic (max 3 attempts)
- [ ] Implement graceful failure handling

### Phase 4: Integration
- [ ] Update `routers/whatsapp.py` - add onboarding check
- [ ] Route to onboarding service if needed
- [ ] Route to external AI service after onboarding
- [ ] Handle onboarding completion transition

### Phase 5: Configuration
- [ ] Update `config.template.json` with onboarding settings
- [ ] Update `config.py` with onboarding config values
- [ ] Copy template to `config.json` if needed

### Phase 6: Testing
- [ ] Write unit tests for `OnboardingService`
- [ ] Test hierarchical scoring algorithm
- [ ] Test ambiguity detection
- [ ] Test selection parsing and handling
- [ ] Write integration tests for WhatsApp flow
- [ ] Test successful onboarding (unique match)
- [ ] Test ambiguous selection workflow
- [ ] Test typo tolerance
- [ ] Test graceful failure (after 3 attempts)
- [ ] Test existing customers skip onboarding
- [ ] Run all tests: `./dc.sh exec backend pytest -v`

### Phase 7: Documentation
- [ ] Update `CLAUDE.md` with onboarding workflow section
- [ ] Add onboarding examples to documentation
- [ ] Document configuration options

---

## 🎯 Success Criteria

1. **✅ Administrative paths fixed** - All paths use human-readable names with `>` separator
2. **✅ Automatic detection** - System detects when customer lacks location data
3. **✅ Smart extraction** - OpenAI accurately extracts province/district/ward
4. **✅ Hierarchical matching** - Correctly matches using administrative paths
5. **✅ Typo tolerance** - Handles misspellings with fuzzy matching
6. **✅ Ambiguity handling** - Shows numbered options for duplicate ward names
7. **✅ Interactive selection** - Farmer can select from 1-5 options
8. **✅ Retry logic works** - Asks clarifying questions up to 3 times
9. **✅ Graceful failure** - Continues normally after failed onboarding
10. **✅ Seamless transition** - Switches to external AI after successful onboarding
11. **✅ No breaking changes** - Existing customers with location skip onboarding
12. **✅ All tests pass** - Unit and integration tests pass

---

## 📊 Example Matching Scenarios

### Scenario 1: Exact Match
```
Farmer: "Kivulini ward, Mwanga district, Kilimanjaro"

Database paths:
1. "Tanzania > Kilimanjaro > Mwanga > Kivulini"     → Score: 100 ✅
2. "Tanzania > Kilimanjaro > Same > Kivulini"       → Score: 66
3. "Tanzania > Arusha > Meru > Kivulini"            → Score: 50

Result: UNIQUE match → Save immediately
```

### Scenario 2: Ambiguous Match
```
Farmer: "Kivulini, Kilimanjaro"

Database paths:
1. "Tanzania > Kilimanjaro > Mwanga > Kivulini"     → Score: 85
2. "Tanzania > Kilimanjaro > Same > Kivulini"       → Score: 85

Difference: 0 points (< 15 threshold)
Result: AMBIGUOUS → Show options
```

### Scenario 3: Typo Tolerance
```
Farmer: "Kivulni ward, Mwaga, Kilimanjro"

Fuzzy matching:
- "Kivulni" vs "Kivulini":    93% (typo: missing 'i')
- "Mwaga" vs "Mwanga":        83% (typo: missing 'n')
- "Kilimanjro" vs "Kilimanjaro": 91% (typo: missing 'a')

Weighted score: (93×3 + 83×2 + 91×1) / 6 = 89 ✅
Result: UNIQUE match despite typos
```

### Scenario 4: No Good Match
```
Farmer: "Somewhere in Tanzania"

Best match: Score 35 (< 75 threshold)
Result: NO MATCH → Ask for clarification
```

---

## 🚨 Important Notes

1. **Administrative Path Format is CRITICAL** - Must run Phase 0 first or fuzzy matching won't work!
2. **Path Format Must Be:** `"Country > Region > District > Ward"` with names, not codes
3. **OpenAI API Key Required** - Onboarding uses OpenAI service for extraction
4. **Administrative Data Required** - Database must have locations populated with correct paths
5. **Fuzzy Matching** - Uses rapidfuzz library (faster than fuzzywuzzy)
6. **Selection Storage** - Stores candidates in database column (supports 10-minute workflow)
7. **Ambiguity Threshold** - Configurable (default: 15 points difference)
8. **Match Score Threshold** - Configurable (default: 75 minimum score)
9. **Both Seeder and Migration Needed** - Seeder for new data, migration for existing data

---

**Status:** Ready for Implementation
**Priority:** High (Core feature for proper farmer registration)
**Dependencies:**
- OpenAI service implementation (OPENAI_SERVICE_IMPLEMENTATION_PLAN.md)
- Administrative data populated in database
**Estimated Effort:** 3-4 days
**CRITICAL:** Phase 0 (administrative path fix) must be completed first!
