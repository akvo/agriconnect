# Implementation Plan 1: Broadcast API Core Implementation

**Date:** 2025-11-08
**Author:** AgriConnect Team
**Status:** Planning
**Objective:** Implement core broadcast messaging infrastructure including database models, schemas, services, and API endpoints

---

## 📊 Overview

### Purpose

Build the foundational broadcast messaging system that allows Extension Officers (EOs) to:
- Create and manage broadcast groups within their ward
- Access groups created by other EOs in the same ward
- Prepare broadcast messages for delivery to multiple groups
- Track broadcast campaigns and recipient lists

### Scope

This plan covers **core infrastructure only**:
- ✅ Database models and migrations
- ✅ Pydantic schemas for validation
- ✅ Business logic services
- ✅ REST API endpoints
- ✅ Unit tests
- ✅ Documentation

**Out of scope** (covered in Plan 2):
- ❌ Twilio WhatsApp integration
- ❌ Two-step template delivery
- ❌ Celery queue processing
- ❌ Webhook handlers
- ❌ Retry logic

---

## 🎯 Design Principles

1. **Ward Isolation**: EOs can only access groups/contacts within their ward
2. **Data Integrity**: Proper foreign keys, constraints, and cascading deletes
3. **Scalability**: Designed for batch processing (max 50 recipients per batch)
4. **Traceability**: Full audit trail with timestamps and creator tracking
5. **Type Safety**: Full Pydantic schema validation
6. **Many-to-Many**: One broadcast can target multiple groups
7. **Status Consistency**: Use existing `DeliveryStatus` enum (not a separate `BroadcastStatus`)
8. **Explicit Confirmation**: Track user confirmation via `confirmed_at` timestamp field

### Status Tracking Strategy

**Decision:** Use existing `DeliveryStatus` enum from `models/message.py`

**Why?**
- ✅ Consistent with regular messages (same enum for all message types)
- ✅ Twilio-aligned (maps directly to WhatsApp delivery callbacks)
- ✅ More granular (includes QUEUED, SENDING states)
- ✅ Simpler codebase (no duplicate enum logic)

**Confirmation Logic:**
- Track user confirmation via `confirmed_at` timestamp (NOT a status enum value)
- When user clicks "Yes": `confirmed_at = datetime.utcnow()`, `status` remains `SENT`
- Query awaiting: `WHERE status = 'SENT' AND confirmed_at IS NULL`
- Query confirmed: `WHERE confirmed_at IS NOT NULL`

**Status Flow:**
```
PENDING → SENT (template) → SENT (confirmed, confirmed_at set) → DELIVERED (actual msg) → READ
```

For detailed rationale, see implementation notes in Phase 1.2.

---

## 📐 API Structure

### Endpoint Organization

```
/api/broadcast/
├── groups                    # Group management
│   ├── POST   /              # Create group
│   ├── GET    /              # List groups
│   ├── GET    /{id}          # Get group details
│   ├── PATCH  /{id}          # Update group
│   └── DELETE /{id}          # Delete group
└── messages                  # Broadcast messages
    ├── POST   /              # Create and send broadcast
    ├── GET    /{id}          # Get broadcast status
    └── GET    /group/{group_id}  # Get all broadcasts for a group
```

---

## 📐 Database Schema

### Architecture Overview

```
broadcast_groups (filter-based segments: "Maize Farmers 20-35", "All Dairy Farmers")
  ↓
  Contains: crop_types JSON [1, 3] and age_groups JSON ["20-35", "36-50"]
  ↓
broadcast_messages (campaign: "New subsidy available!")
  ↓ (many-to-many)
broadcast_message_groups (which groups received this broadcast)
  ↓
broadcast_recipients (delivery tracking per recipient - resolved dynamically)
  ↓
messages (individual message records for history, type=BROADCAST)
```

### Tables to Create

```sql
-- 1. Broadcast Groups (Filter-Based Segments)
CREATE TABLE broadcast_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    crop_types JSON,  -- Array of crop_type IDs: [1, 3, 5]
    age_groups JSON,  -- Array of age group strings: ["20-35", "36-50"]
    administrative_id INTEGER REFERENCES administrative(id),
    created_by INTEGER NOT NULL REFERENCES admin_users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. Broadcast Messages (Campaign Metadata)
CREATE TABLE broadcast_messages (
    id SERIAL PRIMARY KEY,
    message TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES admin_users(id),
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    queued_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 3. Broadcast Message Groups (Many-to-Many: Broadcast → Groups)
CREATE TABLE broadcast_message_groups (
    id SERIAL PRIMARY KEY,
    broadcast_message_id INTEGER NOT NULL REFERENCES broadcast_messages(id) ON DELETE CASCADE,
    broadcast_group_id INTEGER NOT NULL REFERENCES broadcast_groups(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(broadcast_message_id, broadcast_group_id)
);

-- 4. Broadcast Recipients (Delivery Tracking per Recipient)
CREATE TABLE broadcast_recipients (
    id SERIAL PRIMARY KEY,
    broadcast_message_id INTEGER NOT NULL REFERENCES broadcast_messages(id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status VARCHAR(50) DEFAULT 'PENDING',  -- Uses DeliveryStatus: PENDING, QUEUED, SENDING, SENT, DELIVERED, READ, FAILED, UNDELIVERED
    template_message_sid VARCHAR(255),     -- Twilio SID for template message
    actual_message_sid VARCHAR(255),       -- Twilio SID for actual message
    message_id INTEGER REFERENCES messages(id),  -- Link to Message record
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    sent_at TIMESTAMP,
    confirmed_at TIMESTAMP,                -- User clicked "Yes" button (replaces CONFIRMED status)
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 5. Extend MessageType Enum
ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'BROADCAST';

-- 6. Add broadcast_message_id to messages table (link Message → BroadcastMessage)
ALTER TABLE messages ADD COLUMN broadcast_message_id INTEGER REFERENCES broadcast_messages(id);
CREATE INDEX idx_messages_broadcast_message ON messages(broadcast_message_id);

-- Indexes
CREATE INDEX idx_broadcast_groups_administrative ON broadcast_groups(administrative_id);
CREATE INDEX idx_broadcast_groups_created_by ON broadcast_groups(created_by);
CREATE INDEX idx_broadcast_messages_created_by ON broadcast_messages(created_by);
CREATE INDEX idx_broadcast_message_groups_message ON broadcast_message_groups(broadcast_message_id);
CREATE INDEX idx_broadcast_message_groups_group ON broadcast_message_groups(broadcast_group_id);
CREATE INDEX idx_broadcast_recipients_message ON broadcast_recipients(broadcast_message_id);
CREATE INDEX idx_broadcast_recipients_customer ON broadcast_recipients(customer_id);
CREATE INDEX idx_broadcast_recipients_status ON broadcast_recipients(status);
```

---

## 🔧 Implementation Plan

### Phase 1: Database Models and Migration

#### Step 1.1: Extend MessageType Enum

**File:** `backend/models/message.py`

**Changes:**
```python
class MessageType(enum.Enum):
    REPLY = 1      # Reply to farmer
    WHISPER = 2    # Internal suggestion to EO
    BROADCAST = 3  # Broadcast message (NEW)
```

**Location:** Around line 10-15 where MessageType is defined

---

#### Step 1.2: Create Broadcast Models

**File:** `backend/models/broadcast.py` (NEW)

```python
"""
Broadcast models for managing broadcast groups and messages.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Enum
from sqlalchemy.orm import relationship
from database import Base

# Import existing DeliveryStatus from message model
from models.message import DeliveryStatus


class BroadcastGroup(Base):
    """Broadcast Group - Filter-based segment for targeting broadcasts"""
    __tablename__ = "broadcast_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    crop_types = Column(JSON)  # Array of crop_type IDs: [1, 3, 5]
    age_groups = Column(JSON)  # Array of age group strings: ["20-35", "36-50"]
    administrative_id = Column(
        Integer,
        index=True
    )
    created_by = Column(
        Integer,
        index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        onupdate=datetime.utcnow
    )

    # Relationships
    administrative = relationship("Administrative", backref="broadcast_groups")
    creator = relationship("AdminUser", backref="broadcast_groups")
    broadcast_groups = relationship(
        "BroadcastMessageGroup",
        back_populates="broadcast_group"
    )


class BroadcastMessage(Base):


class BroadcastMessage(Base):
    """Broadcast Message - Campaign metadata"""
    __tablename__ = "broadcast_messages"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    created_by = Column(
        Integer,
        ForeignKey("admin_users.id"),
        nullable=False,
        index=True
    )
    status = Column(String(50), default='pending')
    queued_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    creator = relationship("AdminUser", backref="broadcast_messages")
    broadcast_groups = relationship(
        "BroadcastMessageGroup",
        back_populates="broadcast_message",
        cascade="all, delete-orphan"
    )
    broadcast_recipients = relationship(
        "BroadcastRecipient",
        back_populates="broadcast_message",
        cascade="all, delete-orphan"
    )


class BroadcastMessageGroup(Base):
    """Junction table for broadcast → groups (many-to-many)"""
    __tablename__ = "broadcast_message_groups"

    id = Column(Integer, primary_key=True, index=True)
    broadcast_message_id = Column(
        Integer,
        ForeignKey("broadcast_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    broadcast_group_id = Column(
        Integer,
        ForeignKey("broadcast_groups.id"),
        nullable=False,
        index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    broadcast_message = relationship("BroadcastMessage", back_populates="broadcast_groups")
    broadcast_group = relationship("BroadcastGroup", back_populates="broadcast_groups")

    # Constraint
    __table_args__ = (
        UniqueConstraint(
            'broadcast_message_id',
            'broadcast_group_id',
            name='unique_broadcast_message_group'
        ),
    )


class BroadcastRecipient(Base):
    """Delivery tracking for individual recipients"""
    __tablename__ = "broadcast_recipients"

    id = Column(Integer, primary_key=True, index=True)
    broadcast_message_id = Column(
        Integer,
        ForeignKey("broadcast_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
        index=True
    )
    status = Column(
        Enum(DeliveryStatus),
        nullable=False,
        server_default=DeliveryStatus.PENDING.value,
        index=True
    )
    template_message_sid = Column(String(255))
    actual_message_sid = Column(String(255))
    message_id = Column(Integer, ForeignKey("messages.id"))
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    sent_at = Column(DateTime)
    confirmed_at = Column(DateTime)  # When user clicked "Yes" button (replaces CONFIRMED status)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    broadcast_message = relationship("BroadcastMessage", back_populates="broadcast_recipients")
    customer = relationship("Customer")
    message = relationship("Message")
```

---

#### Step 1.3: Create Alembic Migration

**File:** `backend/alembic/versions/2025_11_08_add_broadcast_tables.py` (NEW)

```python
"""Add broadcast tables and extend MessageType enum

Revision ID: add_broadcast_tables
Revises: <previous_revision>
Create Date: 2025-11-08 XX:XX:XX
"""
from alembic import op
import sqlalchemy as sa


revision = 'add_broadcast_tables'
down_revision = '<previous_revision>'  # Update with actual
branch_labels = None
depends_on = None


def upgrade():
    # Extend MessageType enum
    op.execute("ALTER TYPE message_type ADD VALUE IF NOT EXISTS 'BROADCAST'")

    # 1. Create broadcast_groups
    op.create_table(
        'broadcast_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('administrative_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['administrative_id'], ['administrative.id']),
        sa.ForeignKeyConstraint(['created_by'], ['admin_users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_broadcast_groups_administrative', 'broadcast_groups', ['administrative_id'])
    op.create_index('idx_broadcast_groups_created_by', 'broadcast_groups', ['created_by'])

    # 2. Create broadcast_group_contacts
    op.create_table(
        'broadcast_group_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broadcast_group_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['broadcast_group_id'], ['broadcast_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('broadcast_group_id', 'customer_id', name='unique_broadcast_group_contact')
    )
    op.create_index('idx_broadcast_group_contacts_group', 'broadcast_group_contacts', ['broadcast_group_id'])
    op.create_index('idx_broadcast_group_contacts_customer', 'broadcast_group_contacts', ['customer_id'])

    # 3. Create broadcast_messages
    op.create_table(
        'broadcast_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('queued_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['admin_users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_broadcast_messages_created_by', 'broadcast_messages', ['created_by'])

    # 6. Add broadcast_message_id to messages table
    op.add_column('messages', sa.Column('broadcast_message_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_messages_broadcast_message', 'messages', 'broadcast_messages', ['broadcast_message_id'], ['id'])
    op.create_index('idx_messages_broadcast_message', 'messages', ['broadcast_message_id'])

    # 4. Create broadcast_message_groups
    op.create_table(
        'broadcast_message_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broadcast_message_id', sa.Integer(), nullable=False),
        sa.Column('broadcast_group_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['broadcast_message_id'], ['broadcast_messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['broadcast_group_id'], ['broadcast_groups.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('broadcast_message_id', 'broadcast_group_id', name='unique_broadcast_message_group')
    )
    op.create_index('idx_broadcast_message_groups_message', 'broadcast_message_groups', ['broadcast_message_id'])
    op.create_index('idx_broadcast_message_groups_group', 'broadcast_message_groups', ['broadcast_group_id'])

    # 5. Create broadcast_recipients
    op.create_table(
        'broadcast_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broadcast_message_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'QUEUED', 'SENDING', 'SENT', 'DELIVERED', 'READ', 'FAILED', 'UNDELIVERED', name='deliverystatus'),
            server_default='PENDING',
            nullable=False
        ),
        sa.Column('template_message_sid', sa.String(length=255), nullable=True),
        sa.Column('actual_message_sid', sa.String(length=255), nullable=True),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),  # User confirmation timestamp
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['broadcast_message_id'], ['broadcast_messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_broadcast_recipients_message', 'broadcast_recipients', ['broadcast_message_id'])
    op.create_index('idx_broadcast_recipients_customer', 'broadcast_recipients', ['customer_id'])
    op.create_index('idx_broadcast_recipients_status', 'broadcast_recipients', ['status'])


def downgrade():
    op.drop_index('idx_broadcast_recipients_status', 'broadcast_recipients')
    op.drop_index('idx_broadcast_recipients_customer', 'broadcast_recipients')
    op.drop_index('idx_broadcast_recipients_message', 'broadcast_recipients')
    op.drop_table('broadcast_recipients')

    op.drop_index('idx_broadcast_message_groups_group', 'broadcast_message_groups')
    op.drop_index('idx_broadcast_message_groups_message', 'broadcast_message_groups')
    op.drop_table('broadcast_message_groups')

    # Drop messages.broadcast_message_id
    op.drop_index('idx_messages_broadcast_message', 'messages')
    op.drop_constraint('fk_messages_broadcast_message', 'messages', type_='foreignkey')
    op.drop_column('messages', 'broadcast_message_id')

    op.drop_index('idx_broadcast_messages_created_by', 'broadcast_messages')
    op.drop_table('broadcast_messages')

    op.drop_index('idx_broadcast_group_contacts_customer', 'broadcast_group_contacts')
    op.drop_index('idx_broadcast_group_contacts_group', 'broadcast_group_contacts')
    op.drop_table('broadcast_group_contacts')

    op.drop_index('idx_broadcast_groups_created_by', 'broadcast_groups')
    op.drop_index('idx_broadcast_groups_administrative', 'broadcast_groups')
    op.drop_table('broadcast_groups')
```

**Run migration:**
```bash
./dc.sh exec backend alembic upgrade head
```

---

### Phase 2: Schemas and Validation

#### Step 2.1: Create Broadcast Schemas

**File:** `backend/schemas/broadcast.py` (NEW)

```python
"""
Schemas for broadcast group and message management.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator


# ========== Broadcast Group Schemas ==========

class BroadcastGroupCreate(BaseModel):
    """Request schema for creating a broadcast group with filters"""
    name: str = Field(..., min_length=1, max_length=255)
    crop_types: Optional[List[int]] = Field(None, description="Filter by crop type IDs")
    age_groups: Optional[List[str]] = Field(None, description="Filter by age groups: ['20-35', '36-50', '51+']")

    @validator('age_groups')
    def validate_age_groups(cls, v):
        if v:
            valid_groups = ["20-35", "36-50", "51+"]
            for group in v:
                if group not in valid_groups:
                    raise ValueError(f"Invalid age group: {group}. Must be one of {valid_groups}")
        return v


class BroadcastGroupUpdate(BaseModel):
    """Request schema for updating a broadcast group"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    crop_types: Optional[List[int]] = Field(None, description="Filter by crop type IDs")
    age_groups: Optional[List[str]] = Field(None, description="Filter by age groups")

    @validator('age_groups')
    def validate_age_groups(cls, v):
        if v:
            valid_groups = ["20-35", "36-50", "51+"]
            for group in v:
                if group not in valid_groups:
                    raise ValueError(f"Invalid age group: {group}")
        return v


class BroadcastGroupResponse(BaseModel):
    """Response schema for broadcast group"""
    id: int
    name: str
    crop_types: Optional[List[int]]
    age_groups: Optional[List[str]]
    administrative_id: Optional[int]
    created_by: int
    estimated_recipients: int  # Dynamic count based on filters
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BroadcastGroupDetail(BaseModel):
    """Detailed broadcast group response with filter details"""
    id: int
    name: str
    crop_types: Optional[List[int]]
    age_groups: Optional[List[str]]
    administrative_id: Optional[int]
    created_by: int
    estimated_recipients: int  # Dynamic count based on filters
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== Broadcast Message Schemas ==========

class BroadcastMessageCreate(BaseModel):
    """Request schema for creating a broadcast"""
    message: str = Field(..., min_length=1, max_length=1600)
    group_ids: List[int] = Field(..., min_items=1, max_items=10)

    @validator('group_ids')
    def validate_group_ids(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Duplicate group IDs not allowed')
        return v


class BroadcastRecipientStatus(BaseModel):
    """Schema for individual recipient status"""
    customer_id: int
    phone_number: str
    full_name: Optional[str]
    status: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class BroadcastMessageResponse(BaseModel):
    """Response schema for broadcast creation"""
    id: int
    message: str
    status: str
    total_recipients: int
    queued_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class BroadcastMessageStatus(BaseModel):
    """Detailed status of a broadcast"""
    id: int
    message: str
    status: str
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    recipients: List[BroadcastRecipientStatus]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

---

### Phase 3: Services Layer

#### Step 3.1: Create Broadcast Service

**File:** `backend/services/broadcast_service.py` (NEW)

```python
"""
Broadcast service for managing broadcast groups and messages.

NOTE: This is Part 1 - Core operations only.
Celery queue integration will be added in Part 2.
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, distinct

from models.broadcast import (
    BroadcastGroup,
    BroadcastGroupContact,
    BroadcastMessage,
    BroadcastMessageGroup,
    BroadcastRecipient,
)
from models.message import DeliveryStatus
from models.customer import Customer
from models.admin_user import AdminUser

logger = logging.getLogger(__name__)


class BroadcastService:
    def __init__(self, db: Session):
        self.db = db

    # ========== Broadcast Group Management ==========

    def create_group(
        self,
        name: str,
        created_by: int,
        crop_types: Optional[List[int]] = None,
        age_groups: Optional[List[str]] = None,
        administrative_id: Optional[int] = None
    ) -> BroadcastGroup:
        """Create a new broadcast group with filter criteria."""
        group = BroadcastGroup(
            name=name,
            crop_types=crop_types,
            age_groups=age_groups,
            administrative_id=administrative_id,
            created_by=created_by
        )
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)

        # Get estimated recipients
        recipient_count = self.get_group_recipients_count(group)

        logger.info(
            f"Created broadcast group '{name}' (id={group.id}) "
            f"with ~{recipient_count} potential recipients"
        )

        return group

    def get_groups_for_eo(
        self,
        eo_id: int,
        administrative_id: Optional[int] = None
    ) -> List[BroadcastGroup]:
        """Get all broadcast groups visible to an EO."""
        query = self.db.query(BroadcastGroup)

        if administrative_id:
            # Show groups in same ward
            query = query.filter(
                BroadcastGroup.administrative_id == administrative_id
            )
        else:
            # Show only groups created by this EO
            query = query.filter(BroadcastGroup.created_by == eo_id)

        return query.order_by(BroadcastGroup.created_at.desc()).all()

    def get_group_by_id(
        self,
        group_id: int,
        eo_id: int,
        administrative_id: Optional[int] = None
    ) -> Optional[BroadcastGroup]:
        """Get broadcast group by ID with ward access validation."""
        query = self.db.query(BroadcastGroup).filter(
            BroadcastGroup.id == group_id
        )

        if administrative_id:
            query = query.filter(
                BroadcastGroup.administrative_id == administrative_id
            )
        else:
            query = query.filter(BroadcastGroup.created_by == eo_id)

        return query.first()

    def update_group(
        self,
        group_id: int,
        eo_id: int,
        name: Optional[str] = None,
        crop_types: Optional[List[int]] = None,
        age_groups: Optional[List[str]] = None,
        administrative_id: Optional[int] = None
    ) -> Optional[BroadcastGroup]:
        """Update broadcast group (only if EO is owner)."""
        group = self.get_group_by_id(group_id, eo_id, administrative_id)
        if not group:
            return None

        # Only owner can update
        if group.created_by != eo_id:
            logger.warning(
                f"EO {eo_id} attempted to update group {group_id} "
                f"owned by {group.created_by}"
            )
            return None

        # Update fields
        if name is not None:
            group.name = name
        if crop_types is not None:
            group.crop_types = crop_types
        if age_groups is not None:
            group.age_groups = age_groups

        self.db.commit()
        self.db.refresh(group)

        logger.info(f"Updated broadcast group {group_id}")
        return group

    def delete_group(
        self,
        group_id: int,
        eo_id: int,
        administrative_id: Optional[int] = None
    ) -> bool:
        """Delete broadcast group (only if EO is owner)."""
        group = self.get_group_by_id(group_id, eo_id, administrative_id)
        if not group:
            return False

        # Only owner can delete
        if group.created_by != eo_id:
            logger.warning(
                f"EO {eo_id} attempted to delete group {group_id} "
                f"owned by {group.created_by}"
            )
            return False

        self.db.delete(group)
        self.db.commit()

        logger.info(f"Deleted broadcast group {group_id}")
        return True

    def get_group_recipients_count(
        self,
        group: BroadcastGroup
    ) -> int:
        """Get estimated recipient count based on group filters."""
        query = self.db.query(Customer)
        
        # Apply ward filter
        if group.administrative_id:
            query = query.filter(Customer.administrative_id == group.administrative_id)
        
        # Apply crop type filter
        if group.crop_types:
            query = query.filter(Customer.crop_type_id.in_(group.crop_types))
        
        # Apply age group filter
        if group.age_groups:
            query = query.filter(Customer.age_group.in_(group.age_groups))
        
        return query.count()

    # ========== Broadcast Message Creation ==========

    def create_broadcast(
        self,
        message: str,
        group_ids: List[int],
        created_by: int,
        administrative_id: Optional[int] = None
    ) -> Optional[BroadcastMessage]:
        """
        Create broadcast message record (stub for Part 1).

        NOTE: Does not send messages. Celery integration in Part 2.
        """
        # Validate access to all groups
        for group_id in group_ids:
            group = self.get_group_by_id(group_id, created_by, administrative_id)
            if not group:
                logger.error(f"Group {group_id} not accessible")
                return None

        # Get all unique recipients by resolving filters from all groups
        all_recipients = set()
        groups = self.db.query(BroadcastGroup).filter(
            BroadcastGroup.id.in_(group_ids)
        ).all()

        for group in groups:
            query = self.db.query(Customer.id)
            
            # Apply ward filter
            if group.administrative_id:
                query = query.filter(Customer.administrative_id == group.administrative_id)
            
            # Apply crop type filter
            if group.crop_types:
                query = query.filter(Customer.crop_type_id.in_(group.crop_types))
            
            # Apply age group filter
            if group.age_groups:
                query = query.filter(Customer.age_group.in_(group.age_groups))
            
            recipients = query.all()
            all_recipients.update([r.id for r in recipients])

        if not all_recipients:
            logger.error(f"No recipients found for groups {group_ids}")
            return None

        # Create BroadcastMessage
        broadcast = BroadcastMessage(
            message=message,
            created_by=created_by,
            status='pending'
        )
        self.db.add(broadcast)
        self.db.flush()

        # Link to groups (many-to-many)
        for group_id in group_ids:
            link = BroadcastMessageGroup(
                broadcast_message_id=broadcast.id,
                broadcast_group_id=group_id
            )
            self.db.add(link)

        # Create BroadcastRecipient entries for delivery tracking
        for customer_id in all_recipients:
            recipient = BroadcastRecipient(
                broadcast_message_id=broadcast.id,
                customer_id=customer_id,
                status=DeliveryStatus.PENDING
            )
            self.db.add(recipient)

        self.db.commit()
        self.db.refresh(broadcast)

        logger.info(
            f"Created broadcast {broadcast.id} with "
            f"{len(all_recipients)} recipients (not sent yet)"
        )

        return broadcast

    def get_broadcast_status(
        self,
        broadcast_id: int,
        created_by: int
    ) -> Optional[BroadcastMessage]:
        """Get broadcast message with status."""
        broadcast = (
            self.db.query(BroadcastMessage)
            .filter(
                and_(
                    BroadcastMessage.id == broadcast_id,
                    BroadcastMessage.created_by == created_by
                )
            )
            .first()
        )

        return broadcast


def get_broadcast_service(db: Session) -> BroadcastService:
    """Get BroadcastService instance"""
    return BroadcastService(db)
```

---

### Phase 4: API Endpoints

#### Step 4.1: Broadcast Groups Router

**File:** `backend/routers/broadcast_groups.py` (NEW)

```python
"""
Broadcast group management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from routers.auth import get_current_admin_user
from models.admin_user import AdminUser
from models.customer import Customer
from services.broadcast_service import get_broadcast_service
from schemas.broadcast import (
    BroadcastGroupCreate,
    BroadcastGroupUpdate,
    BroadcastGroupResponse,
    BroadcastGroupDetail,
    BroadcastGroupContact
)

router = APIRouter(prefix="/api/broadcast/groups", tags=["Broadcast Groups"])


@router.post(
    "",
    response_model=BroadcastGroupResponse,
    status_code=status.HTTP_201_CREATED
)
def create_broadcast_group(
    group_data: BroadcastGroupCreate,
    current_user: AdminUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new broadcast group with filter criteria."""
    service = get_broadcast_service(db)
    group = service.create_group(
        name=group_data.name,
        crop_types=group_data.crop_types,
        age_groups=group_data.age_groups,
        created_by=current_user.id,
        administrative_id=current_user.administrative_id
    )

    # Get estimated recipient count
    estimated_recipients = service.get_group_recipients_count(group)

    return BroadcastGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        administrative_id=group.administrative_id,
        created_by=group.created_by,
        contact_count=len(group_data.customer_ids),
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@router.get("", response_model=List[BroadcastGroupResponse])
def list_broadcast_groups(
    current_user: AdminUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List all broadcast groups visible to current EO."""
    service = get_broadcast_service(db)
    groups = service.get_groups_for_eo(
        eo_id=current_user.id,
        administrative_id=current_user.administrative_id
    )

    result = []
    for group in groups:
        result.append(BroadcastGroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            administrative_id=group.administrative_id,
            created_by=group.created_by,
            contact_count=len(group.group_contacts),
            created_at=group.created_at,
            updated_at=group.updated_at
        ))

    return result


@router.get("/{group_id}", response_model=BroadcastGroupDetail)
def get_broadcast_group(
    group_id: int,
    current_user: AdminUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a broadcast group."""
    service = get_broadcast_service(db)
    group = service.get_group_by_id(
        group_id=group_id,
        eo_id=current_user.id,
        administrative_id=current_user.administrative_id
    )

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broadcast group not found"
        )

    estimated_recipients = service.get_group_recipients_count(group)

    return BroadcastGroupDetail(
        id=group.id,
        name=group.name,
        crop_types=group.crop_types,
        age_groups=group.age_groups,
        administrative_id=group.administrative_id,
        created_by=group.created_by,
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@router.patch("/{group_id}", response_model=BroadcastGroupResponse)
def update_broadcast_group(
    group_id: int,
    group_data: BroadcastGroupUpdate,
    current_user: AdminUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update broadcast group (owner only)."""
    service = get_broadcast_service(db)
    group = service.update_group(
        group_id=group_id,
        eo_id=current_user.id,
        name=group_data.name,
        crop_types=group_data.crop_types,
        age_groups=group_data.age_groups,
        administrative_id=current_user.administrative_id
    )

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broadcast group not found or not owner"
        )

    estimated_recipients = service.get_group_recipients_count(group)

    return BroadcastGroupResponse(
        id=group.id,
        name=group.name,
        crop_types=group.crop_types,
        age_groups=group.age_groups,
        administrative_id=group.administrative_id,
        created_by=group.created_by,
        estimated_recipients=estimated_recipients,
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@router.get("", response_model=List[BroadcastGroupResponse])
def list_broadcast_groups(
    current_user: AdminUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List all broadcast groups visible to current EO."""
    service = get_broadcast_service(db)
    groups = service.get_groups_for_eo(
        eo_id=current_user.id,
        administrative_id=current_user.administrative_id
    )

    result = []
    for group in groups:
        estimated_recipients = service.get_group_recipients_count(group)
        result.append(BroadcastGroupResponse(
            id=group.id,
            name=group.name,
            crop_types=group.crop_types,
            age_groups=group.age_groups,
            administrative_id=group.administrative_id,
            created_by=group.created_by,
            estimated_recipients=estimated_recipients,
            created_at=group.created_at,
            updated_at=group.updated_at
        ))

    return result


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_broadcast_group(
    group_id: int,
    current_user: AdminUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete broadcast group (owner only)."""
    service = get_broadcast_service(db)
    deleted = service.delete_group(
        group_id=group_id,
        eo_id=current_user.id,
        administrative_id=current_user.administrative_id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broadcast group not found or not owner"
        )
```

---

#### Step 4.2: Broadcast Messages Router

**File:** `backend/routers/broadcast_messages.py` (NEW)

```python
"""
Broadcast message sending API endpoints (stub for Part 1).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from routers.auth import get_current_admin_user
from models.admin_user import AdminUser
from services.broadcast_service import get_broadcast_service
from schemas.broadcast import (
    BroadcastMessageCreate,
    BroadcastMessageResponse,
    BroadcastMessageStatus,
    BroadcastRecipientStatus,
)

router = APIRouter(prefix="/api/broadcast/messages", tags=["Broadcast Messages"])


@router.post(
    "",
    response_model=BroadcastMessageResponse,
    status_code=status.HTTP_202_ACCEPTED
)
def create_broadcast(
    broadcast_data: BroadcastMessageCreate,
    current_user: AdminUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Create broadcast message (stub - does not send yet).

    NOTE: Actual sending will be implemented in Part 2 with Celery.
    """
    service = get_broadcast_service(db)
    broadcast = service.create_broadcast(
        message=broadcast_data.message,
        group_ids=broadcast_data.group_ids,
        created_by=current_user.id,
        administrative_id=current_user.administrative_id
    )

    if not broadcast:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create broadcast"
        )

    return BroadcastMessageResponse(
        id=broadcast.id,
        message=broadcast.message,
        status=broadcast.status,
        total_recipients=len(broadcast.broadcast_recipients),
        queued_at=broadcast.queued_at,
        created_at=broadcast.created_at
    )


@router.get("/{broadcast_id}", response_model=BroadcastMessageStatus)
def get_broadcast_status(
    broadcast_id: int,
    current_user: AdminUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get broadcast status with per-contact delivery tracking."""
    service = get_broadcast_service(db)
    broadcast = service.get_broadcast_status(
        broadcast_id=broadcast_id,
        created_by=current_user.id
    )

    if not broadcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broadcast not found"
        )

    # Calculate counts
    contacts = broadcast.broadcast_recipients
    sent_count = sum(1 for c in contacts if c.sent_at is not None)
    delivered_count = sum(1 for c in contacts if c.delivered_at is not None)
    failed_count = sum(1 for c in contacts if c.status == 'failed')

    # Build contact status list
    contact_statuses = [
        BroadcastRecipientStatus(
            customer_id=c.customer_id,
            phone_number=c.customer.phone_number,
            full_name=c.customer.full_name,
            status=c.status,
            sent_at=c.sent_at,
            delivered_at=c.delivered_at,
            error_message=c.error_message
        )
        for c in contacts
    ]

    return BroadcastMessageStatus(
        id=broadcast.id,
        message=broadcast.message,
        status=broadcast.status,
        total_recipients=len(contacts),
        sent_count=sent_count,
        delivered_count=delivered_count,
        failed_count=failed_count,
        contacts=contact_statuses,
        created_at=broadcast.created_at,
        updated_at=broadcast.updated_at
    )
```

---

#### Step 4.3: Register Routers

**File:** `backend/main.py`

**Add to imports:**
```python
from routers import broadcast_groups, broadcast_messages
```

**Add to router registration:**
```python
app.include_router(broadcast_groups.router)
app.include_router(broadcast_messages.router)
```

---

### Phase 5: Testing

#### Step 5.1: Unit Tests

**File:** `backend/tests/test_broadcast_service.py` (NEW)

```python
"""
Unit tests for broadcast service.
"""
import pytest
from sqlalchemy.orm import Session

from services.broadcast_service import get_broadcast_service
from models.broadcast import BroadcastGroup
from models.admin_user import AdminUser
from models.customer import Customer
from models.administrative import Administrative


@pytest.fixture
def test_ward(db: Session):
    """Create test ward"""
    ward = Administrative(name="Test Ward", level=3)
    db.add(ward)
    db.commit()
    return ward


@pytest.fixture
def test_eo(db: Session, test_ward):
    """Create test EO"""
    eo = AdminUser(
        email="test@example.com",
        username="test_eo",
        administrative_id=test_ward.id
    )
    eo.set_password("password")
    db.add(eo)
    db.commit()
    return eo


@pytest.fixture
def test_customers(db: Session, test_ward):
    """Create test customers"""
    customers = []
    for i in range(5):
        customer = Customer(
            phone_number=f"+62812345{i}",
            full_name=f"Test Customer {i}"
        )
        db.add(customer)
        customers.append(customer)
    db.commit()
    return customers


def test_create_group(db, test_eo, test_customers):
    """Test creating a broadcast group"""
    service = get_broadcast_service(db)
    customer_ids = [c.id for c in test_customers]

    group = service.create_group(
        name="Test Group",
        customer_ids=customer_ids,
        created_by=test_eo.id,
        administrative_id=test_eo.administrative_id
    )

    assert group is not None
    assert group.name == "Test Group"
    assert len(group.group_contacts) == 5


def test_create_broadcast(db, test_eo, test_customers):
    """Test creating broadcast message"""
    service = get_broadcast_service(db)

    # Create group
    group = service.create_group(
        name="Test Group",
        customer_ids=[c.id for c in test_customers],
        created_by=test_eo.id
    )

    # Create broadcast
    broadcast = service.create_broadcast(
        message="Test broadcast message",
        group_ids=[group.id],
        created_by=test_eo.id
    )

    assert broadcast is not None
    assert len(broadcast.broadcast_recipients) == 5
    assert len(broadcast.broadcast_groups) == 1
```

---

### Phase 6: Documentation

**File:** `CLAUDE.md`

Add to API Architecture section:

```markdown
### Broadcast Messaging

AgriConnect includes a broadcast messaging system for Extension Officers.

**Architecture:**
- `broadcast_groups` - Contact lists (e.g., "Maize Farmers")
- `broadcast_messages` - Campaign content
- `broadcast_recipients` - Per-recipient delivery tracking
- Many-to-many: One broadcast → Multiple groups

**API Endpoints:**
- `POST   /api/broadcast/groups` - Create group
- `GET    /api/broadcast/groups` - List groups (ward filtered)
- `GET    /api/broadcast/groups/{id}` - Get group details
- `PATCH  /api/broadcast/groups/{id}` - Update (owner only)
- `DELETE /api/broadcast/groups/{id}` - Delete (owner only)
- `POST   /api/broadcast/messages` - Create broadcast
- `GET    /api/broadcast/messages/{id}` - Get delivery status
```

---

## ✅ Implementation Checklist

### Phase 1: Database
- [ ] Update `models/message.py` - Add BROADCAST enum (ensure DeliveryStatus is exported)
- [ ] Create `models/broadcast.py` with all 5 models (using DeliveryStatus, no BroadcastStatus)
- [ ] Create migration `2025_11_08_add_broadcast_tables.py`
- [ ] Run migration: `./dc.sh exec backend alembic upgrade head`
- [ ] Verify tables created: `psql` and `\dt broadcast*`

### Phase 2: Schemas
- [ ] Create `schemas/broadcast.py`

### Phase 3: Services
- [ ] Create `services/broadcast_service.py`

### Phase 4: API Endpoints
- [ ] Create `routers/broadcast_groups.py`
- [ ] Create `routers/broadcast_messages.py`
- [ ] Register routers in `main.py`

### Phase 5: Testing
- [ ] Create `tests/test_broadcast_service.py`
- [ ] Run tests: `./dc.sh exec backend pytest tests/test_broadcast_service.py -v`

### Phase 6: Documentation
- [ ] Update `CLAUDE.md`
- [ ] Test API via Swagger: http://localhost:8000/api/docs

---

## 🎯 Success Criteria

1. **✅ Database created** - All 5 tables exist with proper relationships
2. **✅ Models work** - Can create groups, link to messages
3. **✅ Ward isolation** - EOs cannot access other wards
4. **✅ Many-to-many** - Broadcasts can target multiple groups
5. **✅ API works** - All endpoints return correct responses
6. **✅ Tests pass** - All unit tests pass
7. **✅ Ready for Part 2** - Structure supports Celery integration

---

## 📊 Database Schema Summary

```
4 Tables:
1. broadcast_groups               - Filter-based segments (crop_types, age_groups JSON)
2. broadcast_messages             - Campaign metadata
3. broadcast_message_groups       - Broadcast → Groups link (many-to-many)
4. broadcast_recipients           - Delivery tracking (resolved dynamically from filters)
```

---

**Status:** Ready for Implementation
**Next:** Part 2 - Twilio Integration with Celery
