# Generic Onboarding System - Implementation Documentation

## Executive Summary

This document describes AgriConnect's **generic, configuration-driven onboarding system** that collects multiple farmer profile fields (administration/ward, crop type, gender, birth year) in a scalable, maintainable way.

**Status**: ✅ **IMPLEMENTED** (as of December 2025)

## Problem Statement

### Previous State

The system initially only collected **administration/ward** information with:
- Single-purpose onboarding focused on location only
- Hard-coded extraction and matching logic
- Limited profile data collection

### Current Solution

A **generic onboarding system** that:
- Collects multiple profile fields in priority order
- Uses configuration-driven field definitions
- Stores extended profile data in JSON for flexibility
- Supports both required and optional fields
- Handles fuzzy matching, ambiguity resolution, and max attempts

### Profile Fields Collected

1. **Administration/Ward** (required) - Priority 1
2. **Crop Type** (required) - Priority 2
3. **Gender** (optional) - Priority 3
4. **Birth Year** (optional) - Priority 4

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│         ONBOARDING FIELD CONFIGURATION                      │
│   (schemas/onboarding_schemas.py - ONBOARDING_FIELDS)      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│            GENERIC ONBOARDING SERVICE                       │
│  (services/onboarding_service.py)                           │
│  - process_onboarding_message() → handles ANY field         │
│  - Field-specific extractors (extract_location, etc.)       │
│  - Field-specific matchers (fuzzy matching for location)    │
│  - AI crop identification (integrated)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              CUSTOMER MODEL (JSON STORAGE)                  │
│  - onboarding_status (overall progress)                     │
│  - current_onboarding_field (which field collecting now)    │
│  - onboarding_candidates (JSON - any field's options)       │
│  - onboarding_attempts (JSON - attempts per field)          │
│  - profile_data (JSONB - stores crop_type, gender, etc.)    │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Customer Model

**File**: `backend/models/customer.py`

```python
class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    language = Column(Enum(CustomerLanguage), default=CustomerLanguage.EN)

    # PROFILE DATA - JSON storage for flexible field management
    profile_data = Column(JSON, nullable=True)
    # Structure: {
    #   "crop_type": "Avocado",
    #   "gender": "male",
    #   "birth_year": 1980
    # }

    # GENERIC ONBOARDING TRACKING
    onboarding_status = Column(
        Enum(OnboardingStatus),
        default=OnboardingStatus.NOT_STARTED,
        nullable=False
    )  # Overall onboarding progress

    current_onboarding_field = Column(String, nullable=True)
    # Current field being collected: "administration", "crop_type", "gender", "birth_year"
    # NULL = not started or completed

    onboarding_candidates = Column(JSON, nullable=True)
    # Ambiguous matches for ANY field (JSON object)
    # Example: {"crop_type": ["Cacao", "Avocado"], "administration": [45, 46]}

    onboarding_attempts = Column(JSON, nullable=True)
    # Attempt counter per field (JSON object)
    # Example: {"administration": 2, "crop_type": 1, "gender": 0}

    # Relationships
    messages = relationship("Message", back_populates="customer")
    customer_administrative = relationship("CustomerAdministrative", back_populates="customer")
    tickets = relationship("Ticket", back_populates="customer")

    # Profile data property accessors
    @property
    def crop_type(self) -> str | None:
        """Get crop_type from profile_data"""
        if not self.profile_data:
            return None
        return self.profile_data.get("crop_type")

    @property
    def gender(self) -> str | None:
        """Get gender from profile_data"""
        if not self.profile_data:
            return None
        return self.profile_data.get("gender")

    @property
    def birth_year(self) -> int | None:
        """Get birth_year from profile_data"""
        if not self.profile_data:
            return None
        return self.profile_data.get("birth_year")

    @property
    def age(self) -> int | None:
        """Calculate current age from birth_year"""
        if not self.birth_year:
            return None
        from datetime import datetime
        current_year = datetime.now().year
        return current_year - self.birth_year

    @property
    def age_group(self) -> str | None:
        """Calculate age group from birth_year"""
        age = self.age
        if age is None:
            return None
        if 20 <= age <= 35:
            return "20-35"
        elif 36 <= age <= 50:
            return "36-50"
        else:
            return "51+"

    # Profile data helper methods
    def get_profile_field(self, field_name: str, default=None):
        """Get a field from profile_data"""
        if not self.profile_data:
            return default
        return self.profile_data.get(field_name, default)

    def set_profile_field(self, field_name: str, value):
        """Set a field in profile_data (triggers SQLAlchemy update)"""
        if not self.profile_data:
            self.profile_data = {}
        profile_dict = self.profile_data.copy()
        profile_dict[field_name] = value
        self.profile_data = profile_dict

    def update_profile_data(self, updates: dict):
        """Update multiple fields in profile_data at once"""
        if not self.profile_data:
            self.profile_data = {}
        profile_dict = self.profile_data.copy()
        profile_dict.update(updates)
        self.profile_data = profile_dict
```

### Enums

```python
class OnboardingStatus(enum.Enum):
    NOT_STARTED = "not_started"   # No fields collected yet
    IN_PROGRESS = "in_progress"   # Currently collecting fields
    COMPLETED = "completed"       # All required fields collected
    FAILED = "failed"             # Max attempts exceeded

class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class AgeGroup(enum.Enum):
    AGE_20_35 = "20-35"
    AGE_36_50 = "36-50"
    AGE_51_PLUS = "51+"
```

**Note**: `AgeGroup` enum exists for legacy compatibility but is not stored in the database. Age group is calculated dynamically from `birth_year` via the `@property age_group` method.

### Legacy Models

**File**: `backend/models/customer.py`

```python
class CropType(Base):
    """
    Legacy model - TABLE DROPPED in migration 608c46cd8d4f.

    Kept for code compatibility only. Crop types now stored as strings
    in profile_data and configured in config.json.
    """
    __tablename__ = "crop_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## Database Migrations

### Migration 1: Generic Onboarding Fields

**File**: `backend/alembic/versions/2025_12_02_0337-65e511681dc7_add_generic_onboarding_fields.py`

**Changes**:
1. Added `current_onboarding_field` column (String)
2. Converted `onboarding_attempts`: Integer → JSON
3. Converted `onboarding_candidates`: Text → JSON
4. Added `profile_data` JSONB column
5. Migrated existing data to `profile_data`
6. Dropped `age_group` and `age` columns
7. Migrated `crop_type_id` data to `profile_data.crop_type`
8. Added GIN index on `profile_data` for JSON queries

```python
def upgrade() -> None:
    """Upgrade to profile_data JSON storage system"""
    connection = op.get_bind()

    # 1. Add current_onboarding_field column
    op.add_column(
        "customers",
        sa.Column("current_onboarding_field", sa.String(), nullable=True),
    )

    # 2. Convert onboarding_attempts: Integer → JSON
    op.add_column(
        "customers",
        sa.Column("onboarding_attempts_json", sa.JSON(), nullable=True),
    )
    connection.execute(sa.text("""
        UPDATE customers
        SET onboarding_attempts_json =
            CASE
                WHEN onboarding_attempts > 0
                THEN json_build_object('administration', onboarding_attempts)
                ELSE '{}'::json
            END
    """))
    op.drop_column("customers", "onboarding_attempts")
    op.alter_column("customers", "onboarding_attempts_json",
                    new_column_name="onboarding_attempts")

    # 3. Convert onboarding_candidates: Text → JSON
    op.add_column(
        "customers",
        sa.Column("onboarding_candidates_json", sa.JSON(), nullable=True),
    )
    connection.execute(sa.text("""
        UPDATE customers
        SET onboarding_candidates_json =
            CASE
                WHEN onboarding_candidates IS NOT NULL
                    AND onboarding_candidates != ''
                    AND onboarding_candidates != 'null'
                    AND onboarding_candidates::text ~ '^\\[.*\\]$'
                THEN json_build_object('administration', onboarding_candidates::json)
                ELSE NULL
            END
        WHERE onboarding_candidates IS NOT NULL
    """))
    op.drop_column("customers", "onboarding_candidates")
    op.alter_column("customers", "onboarding_candidates_json",
                    new_column_name="onboarding_candidates")

    # 4. Add profile_data JSONB column
    op.add_column(
        "customers",
        sa.Column("profile_data", postgresql.JSONB, nullable=True),
    )

    # 5. Migrate crop_type_id to profile_data
    connection.execute(sa.text("""
        UPDATE customers c
        SET profile_data = COALESCE(profile_data, '{}'::jsonb) ||
            jsonb_build_object('crop_type', ct.name)
        FROM crop_types ct
        WHERE c.crop_type_id = ct.id
            AND c.crop_type_id IS NOT NULL
    """))
    op.drop_column("customers", "crop_type_id")

    # 6. Drop age_group and age columns
    op.drop_column("customers", "age_group")
    op.drop_column("customers", "age")

    # 7. Add GIN index for JSON queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customers_profile_data "
        "ON customers USING gin (profile_data)"
    )
```

### Migration 2: Drop Crop Types Table

**File**: `backend/alembic/versions/2025_12_03_0323-608c46cd8d4f_drop_crop_types_table.py`

**Changes**:
1. Dropped `crop_types` table
2. Dropped index `ix_crop_types_id`

```python
def upgrade() -> None:
    op.drop_index(op.f('ix_crop_types_id'), table_name='crop_types')
    op.drop_table('crop_types')

def downgrade() -> None:
    op.create_table(
        'crop_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_crop_types_id'), 'crop_types', ['id'], unique=False)
```

---

## Crop Types Configuration

Crop types are configured in JSON and validated using AI, providing:

✅ **Simplicity**: No database migrations to add/remove crops
✅ **Version Control**: Changes tracked in git
✅ **AI-Powered**: Handles spelling, translations, and variations
✅ **Performance**: No fuzzy matching needed
✅ **Flexibility**: Easy to update via config

### Configuration File

**File**: `backend/config.template.json` (and `backend/config.json`)

```json
{
  "crop_types": [
    "Avocado",
    "Cacao"
  ]
}
```

### Configuration Access

**File**: `backend/config.py`

```python
class Settings(BaseSettings):
    # Crop types configuration
    crop_types: list = _config.get("crop_types", ["Avocado", "Cacao"])

# Global settings instance
settings = Settings()
```

### Crop Types API Endpoint

**File**: `backend/routers/crop_types.py`

Maintains backward compatibility with mobile app by reading from config instead of database:

```python
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.customer import CropTypeInfo
from config import settings

router = APIRouter(prefix="/crop-types", tags=["crop-types"])

@router.get("/", response_model=List[CropTypeInfo])
async def get_crop_types(db: Session = Depends(get_db)):
    """
    Get all crop types from configuration.

    Uses array index + 1 as ID for backward compatibility.
    """
    crop_types = settings.crop_types
    return [
        {
            "id": index + 1,  # 1-based indexing
            "name": crop_type
        }
        for index, crop_type in enumerate(crop_types)
    ]
```

**Example Response**:
```json
[
  {"id": 1, "name": "Avocado"},
  {"id": 2, "name": "Cacao"}
]
```

**Note**: The `id` field is virtual (derived from array index) and not stored in the database. The Customer model stores only the crop name as a string in `profile_data`.

---

## Onboarding Field Configuration

**File**: `backend/schemas/onboarding_schemas.py`

All onboarding fields are defined in a configuration list:

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class OnboardingFieldConfig:
    """Configuration for a single onboarding field"""
    field_name: str          # Unique identifier: "administration", "crop_type", etc.
    db_field: str            # Database field: "customer_administrative", "crop_type", etc.
    required: bool           # Required for onboarding completion
    priority: int            # Collection order (1 = first)
    initial_question: str    # Question to ask farmer
    extraction_method: str   # Method name in OnboardingService
    matching_method: Optional[str]  # Ambiguity resolution method (optional)
    max_attempts: int        # Max attempts before skip/fail
    field_type: str          # "location", "string", "enum", "integer"
    success_message_template: str  # Success message with {value} placeholder

# ONBOARDING FIELDS REGISTRY
ONBOARDING_FIELDS: List[OnboardingFieldConfig] = [
    # PRIORITY 1: Administration Location (REQUIRED)
    OnboardingFieldConfig(
        field_name="administration",
        db_field="customer_administrative",
        required=True,
        priority=1,
        initial_question=(
            "Welcome! To connect you with the right agricultural expert, "
            "I need to know your location.\n\n"
            "Please tell me: What ward or village are you from?"
        ),
        extraction_method="extract_location",
        matching_method="resolve_administration_ambiguity",
        max_attempts=3,
        field_type="location",
        success_message_template="Perfect! I've noted that you're in {value}.",
    ),

    # PRIORITY 2: Crop Type (REQUIRED)
    OnboardingFieldConfig(
        field_name="crop_type",
        db_field="crop_type",
        required=True,
        priority=2,
        initial_question=(
            "What crops do you grow?\n\n"
            "We currently support: {available_crops}\n\n"
            "Please tell me which crop you grow."
        ),
        extraction_method="extract_crop_type",
        matching_method="resolve_crop_ambiguity",
        max_attempts=3,
        field_type="string",
        success_message_template="Great! I've noted that you grow {value}.",
    ),

    # PRIORITY 3: Gender (OPTIONAL)
    OnboardingFieldConfig(
        field_name="gender",
        db_field="gender",
        required=False,
        priority=3,
        initial_question=(
            "To help us serve you better, may I know your gender?\n\n"
            "You can say: male, female, or other"
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
            "What year were you born? "
            "You can also tell me your age if that's easier.\n\n"
            "For example: '1980' or 'I'm 45 years old'"
        ),
        extraction_method="extract_birth_year",
        matching_method=None,  # AI converts age to birth year
        max_attempts=2,
        field_type="integer",
        success_message_template="Got it, thank you!",
    ),
]

# Helper functions
def get_field_config(field_name: str) -> Optional[OnboardingFieldConfig]:
    """Get configuration for a specific field by name"""
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
    """Get all fields sorted by priority (ascending)"""
    return sorted(ONBOARDING_FIELDS, key=lambda x: x.priority)
```

---

## Onboarding Service Implementation

**File**: `backend/services/onboarding_service.py`

The service handles all field collection generically based on configuration.

### Service Architecture

```python
class OnboardingService:
    """Generic service for AI-driven farmer onboarding"""

    def __init__(self, db: Session):
        self.db = db
        self.openai_service = get_openai_service()
        self.fields_config = get_fields_by_priority()
        self.supported_crops = settings.crop_types

        # Fuzzy matching configuration
        self.match_threshold = 60.0
        self.ambiguity_threshold = 15.0
        self.max_candidates = 5

    # PUBLIC INTERFACE
    def needs_onboarding(self, customer: Customer) -> bool
    async def process_onboarding_message(self, customer: Customer, message: str) -> OnboardingResponse

    # FIELD EXTRACTION METHODS
    async def extract_location(self, message: str) -> Optional[LocationData]
    async def extract_crop_type(self, message: str) -> Optional[str]
    async def extract_gender(self, message: str) -> Optional[str]
    async def extract_birth_year(self, message: str) -> Optional[int]

    # MATCHING METHODS
    def find_matching_wards(self, location: LocationData) -> List[MatchCandidate]
    async def resolve_crop_ambiguity(self, message: str, candidates: List[str]) -> Optional[str]

    # STATE MANAGEMENT
    def _get_next_incomplete_field(self, customer: Customer) -> Optional[OnboardingFieldConfig]
    def _is_field_complete(self, customer: Customer, field_config: OnboardingFieldConfig) -> bool
    def _increment_attempts(self, customer: Customer, field_name: str)
    def _get_attempts(self, customer: Customer, field_name: str) -> int
    def _store_candidates(self, customer: Customer, field_name: str, candidates: List[Any])
    def _clear_field_state(self, customer: Customer, field_name: str)
```

### Main Processing Flow

```python
async def process_onboarding_message(
    self,
    customer: Customer,
    message: str
) -> OnboardingResponse:
    """
    Main entry point for onboarding messages.

    Flow:
    1. Get next incomplete field
    2. Check if awaiting selection (ambiguous match)
    3. Check if first message for field → ask initial question
    4. Extract value from message
    5. Match/validate value (for fields with matching)
    6. Save value or present options
    7. Move to next field or complete onboarding
    """
    # Get next field to collect
    next_field_config = self._get_next_incomplete_field(customer)

    if next_field_config is None:
        return self._complete_onboarding(customer)

    field_name = next_field_config.field_name

    # Handle selection from previous ambiguous match
    if self._is_awaiting_selection(customer, field_name):
        return await self._process_selection(customer, message, next_field_config)

    # Ask initial question if starting new field
    if customer.current_onboarding_field != field_name:
        return self._ask_initial_question(customer, next_field_config)

    # Process farmer's answer
    return await self._process_field_value(customer, message, next_field_config)
```

### Field Value Processing

```python
async def _process_field_value(
    self,
    customer: Customer,
    message: str,
    field_config: OnboardingFieldConfig,
) -> OnboardingResponse:
    """
    Extract and process field value from farmer's message.

    Handles:
    - location: Extract → Fuzzy match → Handle ambiguity/no match
    - string: Extract → Validate → Save
    - enum: Extract → Validate → Save
    - integer: Extract → Validate → Save
    """
    field_name = field_config.field_name

    # Allow skipping optional fields
    if not field_config.required and message.lower().strip() in [
        "skip", "pass", "next", "no", "n/a", "na"
    ]:
        customer.set_profile_field(field_name, None)
        self._clear_field_state(customer, field_name)
        self.db.commit()

        next_field = self._get_next_incomplete_field(customer)
        if next_field:
            return self._ask_initial_question(customer, next_field)
        else:
            return self._complete_onboarding(customer)

    # Increment attempts
    current_attempts = self._get_attempts(customer, field_name)
    self._increment_attempts(customer, field_name)
    self.db.commit()

    # Check max attempts
    new_attempts = self._get_attempts(customer, field_name)
    if new_attempts > field_config.max_attempts:
        return await self._handle_max_attempts(customer, field_config, message)

    # Extract value using configured method
    try:
        extraction_method = getattr(self, field_config.extraction_method)
        extracted_value = await extraction_method(message)
    except Exception as e:
        logger.error(f"Extraction failed for {field_name}: {e}")
        return OnboardingResponse(
            message=f"I didn't understand. {field_config.initial_question}",
            status="in_progress",
            attempts=new_attempts,
        )

    # Handle extraction failure
    if extracted_value is None:
        return OnboardingResponse(
            message=f"I couldn't identify that information. {field_config.initial_question}",
            status="in_progress",
            attempts=new_attempts,
        )

    # Handle based on field type
    if field_config.field_type == "location":
        return await self._handle_location_field(customer, extracted_value, field_config)
    else:
        return self._save_field_value(customer, extracted_value, field_config)
```

### Saving Field Values

```python
def _save_field_value(
    self,
    customer: Customer,
    value: Any,
    field_config: OnboardingFieldConfig,
) -> OnboardingResponse:
    """
    Save field value to database and move to next field.

    Handles:
    - administration: Saves to CustomerAdministrative relationship table
    - Other fields: Saves to profile_data JSON
    """
    field_name = field_config.field_name

    try:
        # Special case: administration uses relationship table
        if field_name == "administration":
            existing = (
                self.db.query(CustomerAdministrative)
                .filter_by(customer_id=customer.id)
                .first()
            )
            if existing:
                existing.administrative_id = value.id
            else:
                customer_admin = CustomerAdministrative(
                    customer_id=customer.id,
                    administrative_id=value.id,
                )
                self.db.add(customer_admin)
            success_msg = field_config.success_message_template.format(value=value.path)

        # Standard case: save to profile_data JSON
        else:
            if not customer.profile_data:
                customer.profile_data = {}
            elif not isinstance(customer.profile_data, dict):
                customer.profile_data = {}

            profile_dict = customer.profile_data.copy()

            # Convert enum to value if needed
            if isinstance(value, Gender):
                profile_dict[field_name] = value.value
            else:
                profile_dict[field_name] = value

            customer.profile_data = profile_dict
            success_msg = field_config.success_message_template.format(value=value)

        # Clear field state
        self._clear_field_state(customer, field_name)
        self.db.commit()

        # Move to next field or complete
        next_field = self._get_next_incomplete_field(customer)

        if next_field:
            # Combine success message with next question
            combined_message = f"{success_msg}\n\n{next_field.initial_question}"
            if next_field.field_name == "crop_type":
                crops_formatted = ", ".join(crop.lower() for crop in self.supported_crops)
                combined_message = combined_message.replace("{available_crops}", crops_formatted)
            customer.current_onboarding_field = next_field.field_name
            self.db.commit()

            return OnboardingResponse(
                message=combined_message,
                status="in_progress",
                attempts=self._get_attempts(customer, next_field.field_name),
            )
        else:
            return self._complete_onboarding(customer)

    except Exception as e:
        logger.error(f"Failed to save {field_name}: {e}")
        self.db.rollback()
        return OnboardingResponse(
            message="Sorry, I had trouble saving that. Please try again.",
            status="in_progress",
            attempts=self._get_attempts(customer, field_name),
        )
```

### AI Crop Identification (Integrated)

The crop identification logic is **integrated directly into OnboardingService** (not a separate service file):

```python
async def extract_crop_type(self, message: str) -> Optional[str]:
    """
    Extract crop type from message using AI.

    Handles:
    - Spelling mistakes
    - Translations (English/Swahili)
    - Local names and variations
    """
    result = await self._identify_crop(message)

    if (
        result.crop_name and
        result.crop_name.strip().lower() in [c.lower() for c in self.supported_crops]
    ):
        return result.crop_name

    return None

async def _identify_crop(
    self,
    message: str,
    conversation_context: Optional[str] = None
) -> CropIdentificationResult:
    """
    Identify crop type using AI with structured output.

    Returns:
        CropIdentificationResult with crop_name and confidence
    """
    system_prompt = self._build_crop_identification_prompt()

    user_message = message
    if conversation_context:
        user_message = f"Previous context: {conversation_context}\n\nFarmer's message: {message}"

    try:
        response = await self.openai_service.structured_output(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format=CropIdentificationResult,
        )

        if not response:
            return CropIdentificationResult(
                crop_name=None,
                confidence="low",
                possible_crops=[]
            )

        result = CropIdentificationResult(**response.data)

        if result.crop_name:
            result.crop_name = self._normalize_crop_name(result.crop_name)

        return result

    except Exception as e:
        logger.error(f"Error identifying crop: {e}")
        return CropIdentificationResult(
            crop_name=None,
            confidence="low",
            possible_crops=[]
        )

def _build_crop_identification_prompt(self) -> str:
    """Build system prompt for crop identification"""
    crops_list = ", ".join(self.supported_crops)

    return f"""You are an agricultural assistant helping to identify crop types.

SUPPORTED CROPS:
{crops_list}

TASK:
Extract the primary crop type mentioned in the farmer's message.

RULES:
1. Match to ONE of the supported crops listed above
2. Use exact crop names from the supported list
3. Handle common variations (e.g., "maize" = "Maize", "corn" = "Maize")
4. If multiple crops mentioned, extract the PRIMARY/MAIN one
5. Set confidence: "high", "medium", or "low"
6. If ambiguous, list possible matches in possible_crops
7. If no crop mentioned, set crop_name to null

EXAMPLES:
- "I grow coffee" → crop_name: "Coffee", confidence: "high"
- "Maize farming" → crop_name: "Maize", confidence: "high"
- "I'm a farmer" → crop_name: null, confidence: "low"
"""
```

---

## Integration with WhatsApp Webhook

**File**: `backend/routers/whatsapp.py`

The webhook uses the generic onboarding service:

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

## Adding New Fields (Future)

To add a new profile field (e.g., "farm_size"):

### 1. Add Field to Configuration

**File**: `backend/schemas/onboarding_schemas.py`

```python
ONBOARDING_FIELDS.append(
    OnboardingFieldConfig(
        field_name="farm_size",
        db_field="farm_size",  # Will be stored in profile_data
        required=False,
        priority=5,
        initial_question="How large is your farm in hectares?",
        extraction_method="extract_farm_size",
        matching_method=None,
        max_attempts=2,
        field_type="integer",
        success_message_template="Thank you! I've noted your farm is {value} hectares.",
    )
)
```

### 2. Add Extraction Method

**File**: `backend/services/onboarding_service.py`

```python
async def extract_farm_size(self, message: str) -> Optional[float]:
    """Extract farm size from message"""
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

    response = await self.openai_service.structured_output(
        messages=messages,
        response_format={
            "type": "object",
            "properties": {
                "farm_size": {"type": ["number", "null"]},
            },
        },
    )

    if not response or not response.data.get("farm_size"):
        return None

    return response.data["farm_size"]
```

**That's it!** No database migrations, no service logic changes. The field is automatically stored in `profile_data` JSON and collected in priority order.

---

## Benefits of Current Implementation

### JSON Storage (`profile_data`)

✅ **No Migrations**: Add new fields without schema changes
✅ **Flexibility**: Store complex data types (arrays, nested objects)
✅ **Rapid Iteration**: Test fields in production quickly
✅ **Field Versioning**: Easy to deprecate/rename fields
✅ **Query Performance**: PostgreSQL JSONB with GIN indexing

### Configuration-Driven

✅ **Single Source of Truth**: All fields defined in one place
✅ **Easy to Extend**: Add fields by updating config only
✅ **Maintainable**: No duplicate service code
✅ **Testable**: Field logic isolated and testable

### AI-Powered Extraction

✅ **Intelligent Matching**: Handles spelling, translations, variations
✅ **No Fuzzy Matching**: AI understands context
✅ **Language Agnostic**: Works with English, Swahili, mixed input
✅ **Adaptive**: Learns from context and conversation history

---

## File Structure Summary

```
backend/
├── models/
│   └── customer.py              # Customer model with profile_data JSON
├── schemas/
│   └── onboarding_schemas.py    # ONBOARDING_FIELDS configuration
├── services/
│   └── onboarding_service.py    # Generic onboarding service (AI crop integrated)
├── routers/
│   ├── whatsapp.py              # WhatsApp webhook integration
│   └── crop_types.py            # Crop types API (reads from config)
├── alembic/versions/
│   ├── 2025_12_02_0337-65e511681dc7_add_generic_onboarding_fields.py
│   └── 2025_12_03_0323-608c46cd8d4f_drop_crop_types_table.py
├── config.py                     # Settings with crop_types list
└── config.template.json          # Configuration template with crop_types
```

---

## Testing

Run tests with:

```bash
./dc.sh exec backend pytest tests/test_onboarding_service.py -v
```

Key test scenarios:
- Field priority ordering
- Required vs optional field handling
- Ambiguous match resolution
- Max attempts handling
- Skip optional fields
- Birth year extraction (year, age, ranges)
- Age calculation from birth_year
- Age group calculation from birth_year
- JSON state management

---

## Future Enhancements

1. **Profile Data Analytics**: Query profile_data for insights
2. **Field Validation Rules**: Add min/max constraints to config
3. **Conditional Fields**: Show fields based on previous answers
4. **Multi-Value Fields**: Support arrays (e.g., multiple crops)
5. **Field Dependencies**: Chain fields logically
6. **Admin UI**: Manage fields via web interface
7. **Field Versioning**: Track schema changes over time

---

## Summary

The generic onboarding system provides a **scalable, maintainable** approach to collecting farmer profile data:

- **Configuration-driven**: Add fields without code changes
- **JSON storage**: No migrations for new fields
- **AI-powered**: Intelligent extraction and matching
- **Priority-based**: Collect fields in defined order
- **Flexible**: Support required and optional fields
- **Extensible**: Easy to add new field types

This architecture supports AgriConnect's growth while maintaining code quality and developer velocity.
