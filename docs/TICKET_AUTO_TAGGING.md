# Ticket Auto-Tagging Implementation

**Date:** 2026-01-22
**Author:** AgriConnect Team
**Status:** Implemented
**Objective:** Automatically classify closed tickets using AI for analytics purposes

---

## 📊 Overview

### Purpose

Enable automatic categorization of support tickets when they are closed by Extension Officers (EOs). This provides valuable analytics data about the types of agricultural questions and issues farmers are asking about.

### Key Principle

**Tagging happens at ticket closure** - The conversation is analyzed by OpenAI when the EO closes the ticket, and a category tag is assigned with a confidence score.

### User Experience

```
EO closes ticket →
    System fetches conversation →
    OpenAI classifies content →
    Tag + confidence saved →
    Admin sees analytics
```

### Tag Categories

| Tag | ID | Description |
|-----|------|-------------|
| FERTILIZER | 1 | Questions about fertilizers, soil nutrients, composting, manure, NPK ratios, or nutrient deficiencies |
| PEST | 2 | Questions about pests, insects, diseases, fungal infections, pest control, pesticides, or crop damage |
| PRE_PLANTING | 3 | Questions about seed selection, land preparation, planting timing, soil testing, or seedbed preparation |
| HARVESTING | 4 | Questions about harvest timing, post-harvest handling, storage, drying, or crop maturity |
| IRRIGATION | 5 | Questions about watering, irrigation systems, drought management, water conservation, or flooding |
| OTHER | 6 | Questions that don't fit the above categories |

---

## 🎯 Design Principles

1. **Non-blocking** - Tagging happens during close action but doesn't block the operation
2. **Graceful Degradation** - If OpenAI fails, ticket still closes without tag
3. **Confidence Tracking** - Store AI confidence score for quality monitoring
4. **Admin Analytics** - Provide aggregate statistics for reporting
5. **Access Control** - Respect administrative area restrictions

---

## 📐 Architecture Design

### Auto-Tagging Flow

```
┌─────────────────────────────────────────────────────────────┐
│         PATCH /api/tickets/{ticket_id}                      │
│         payload: { "resolved_at": "2026-01-22T10:00:00Z" }  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Validate Request    │
              │  - Ticket exists     │
              │  - User has access   │
              │  - Not already closed│
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Fetch Conversation  │
              │  - Get ticket message│
              │  - Query all messages│
              │  - Since escalation  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Classify with AI    │
              │  - Build prompt      │
              │  - Call OpenAI       │
              │  - Parse response    │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Update Ticket       │
              │  - resolved_at       │
              │  - resolved_by       │
              │  - tag (1-6)         │
              │  - tag_confidence    │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Emit WebSocket      │
              │  - ticket_resolved   │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Return Response     │
              │  - ticket with tag   │
              └──────────────────────┘
```

### Database Schema

#### Ticket Model Updates

**File:** `backend/models/ticket.py`

```python
import enum

class TicketTag(enum.IntEnum):
    """Tag categories for ticket classification"""
    FERTILIZER = 1
    PEST = 2
    PRE_PLANTING = 3
    HARVESTING = 4
    IRRIGATION = 5
    OTHER = 6


class Ticket(Base):
    __tablename__ = "tickets"

    # ... existing fields ...

    tag = Column(Integer, nullable=True)  # TicketTag enum value
    tag_confidence = Column(Float, nullable=True)  # AI confidence 0.0-1.0
```

**Migration:** `backend/alembic/versions/2026_01_22_1000-d7e8f9a0b1c2_add_ticket_tag_columns.py`

---

## 🔧 Implementation Details

### Phase 1: Database Schema

#### Migration File

**File:** `backend/alembic/versions/2026_01_22_1000-d7e8f9a0b1c2_add_ticket_tag_columns.py`

```python
"""Add ticket tag columns for auto-tagging

Revision ID: d7e8f9a0b1c2
Revises: c9e8f7d6b5a4
Create Date: 2026-01-22 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c9e8f7d6b5a4"

def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("tag", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("tag_confidence", sa.Float(), nullable=True),
    )
    op.create_index("idx_tickets_tag", "tickets", ["tag"])

def downgrade() -> None:
    op.drop_index("idx_tickets_tag", "tickets")
    op.drop_column("tickets", "tag_confidence")
    op.drop_column("tickets", "tag")
```

---

### Phase 2: Tagging Service

**File:** `backend/services/tagging_service.py`

```python
"""
Tagging Service for automatic ticket classification.

Uses OpenAI to analyze conversation content and classify tickets
into predefined categories for analytics purposes.
"""

from typing import Optional, List, Dict, Any
from models.ticket import TicketTag
from services.openai_service import get_openai_service

# Tag descriptions for AI context
TAG_DESCRIPTIONS = {
    TicketTag.FERTILIZER: "Questions about fertilizers, soil nutrients...",
    TicketTag.PEST: "Questions about pests, insects, diseases...",
    TicketTag.PRE_PLANTING: "Questions about seed selection, land preparation...",
    TicketTag.HARVESTING: "Questions about harvest timing, post-harvest...",
    TicketTag.IRRIGATION: "Questions about watering, irrigation systems...",
    TicketTag.OTHER: "Questions that don't fit the above categories...",
}


class TaggingResult:
    """Result of ticket tagging operation"""
    def __init__(self, tag: TicketTag, confidence: float, reason: str = None):
        self.tag = tag
        self.confidence = confidence
        self.reason = reason


async def classify_ticket(
    messages: List[Dict[str, Any]],
) -> Optional[TaggingResult]:
    """
    Classify a ticket based on conversation messages.

    Args:
        messages: List of message dicts with 'body' and 'from_source'

    Returns:
        TaggingResult with tag, confidence, and optional reason
    """
    openai_service = get_openai_service()

    if not openai_service.is_configured():
        return None

    # Build conversation text
    conversation_text = _build_conversation_text(messages)

    # Build classification prompt with tag options
    tag_options = "\n".join([
        f"- {tag.name}: {desc}"
        for tag, desc in TAG_DESCRIPTIONS.items()
    ])

    system_prompt = f"""You are an agricultural support ticket classifier.
Analyze the conversation and classify it into ONE of these categories:

{tag_options}

Respond with valid JSON:
{{"tag": "CATEGORY_NAME", "confidence": 0.85, "reason": "brief explanation"}}
"""

    # Call OpenAI structured_output
    response = await openai_service.structured_output(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": conversation_text},
        ],
        response_format={"type": "json_object"},
    )

    # Parse and return result
    if response and response.data:
        tag_name = response.data.get("tag", "OTHER").upper()
        confidence = float(response.data.get("confidence", 0.5))
        reason = response.data.get("reason", "")

        try:
            tag = TicketTag[tag_name]
        except KeyError:
            tag = TicketTag.OTHER

        return TaggingResult(tag=tag, confidence=confidence, reason=reason)

    return None
```

---

### Phase 3: Router Integration

**File:** `backend/routers/tickets.py` (modified)

```python
from services.tagging_service import classify_ticket, get_tag_name

# In _serialize_ticket function, add:
{
    # ... existing fields ...
    "tag": get_tag_name(ticket.tag) if ticket.tag else None,
    "tag_confidence": ticket.tag_confidence,
}

# In mark_ticket_resolved endpoint, add before db.commit():
# Fetch conversation messages
msgs = db.query(Message).filter(
    Message.customer_id == ticket.customer_id,
    Message.created_at >= ticket_message.created_at,
).order_by(Message.created_at.asc()).limit(50).all()

# Build message list for tagging
messages_for_tagging = [
    {"body": m.body, "from_source": get_from_source_string(m.from_source)}
    for m in msgs
]

# Classify the ticket
tagging_result = await classify_ticket(messages_for_tagging)
if tagging_result:
    ticket.tag = tagging_result.tag.value
    ticket.tag_confidence = tagging_result.confidence
```

---

### Phase 4: Admin Analytics Endpoint

**File:** `backend/routers/admin_analytics.py`

```python
"""
Admin Analytics Router for ticket tag statistics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


@router.get("/ticket-tags")
async def get_ticket_tag_statistics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get ticket tag statistics for analytics.

    Returns count of tickets per tag category.
    Admin users see all tickets, EO users see only their areas.
    """
    query = db.query(
        Ticket.tag,
        func.count(Ticket.id).label("count"),
    ).filter(
        Ticket.resolved_at.isnot(None),
        Ticket.tag.isnot(None),
    )

    # Apply access control and date filters...

    results = query.group_by(Ticket.tag).all()

    return {
        "statistics": [
            {"tag": tag.name.lower(), "tag_id": tag.value, "count": count}
            for tag, count in results
        ],
        "total_tagged": sum(count for _, count in results),
        "total_resolved": total_resolved,
        "untagged_count": total_resolved - total_tagged,
    }


@router.get("/ticket-tags/available")
async def get_available_tags(
    current_user: User = Depends(get_current_user),
):
    """Get list of available ticket tags with descriptions."""
    return {"tags": get_all_tags()}
```

---

## 📡 API Reference

### Auto-Tag on Close (Existing Endpoint)

**Endpoint:** `PATCH /api/tickets/{ticket_id}`

**Request:**
```json
{
  "resolved_at": "2026-01-22T10:00:00Z"
}
```

**Response:**
```json
{
  "ticket": {
    "id": 123,
    "ticket_number": "20260122100000",
    "status": "resolved",
    "resolved_at": "2026-01-22T10:00:00Z",
    "tag": "pest",
    "tag_confidence": 0.92,
    "customer": { ... },
    "message": { ... },
    "resolver": { ... }
  }
}
```

---

### Get Tag Statistics

**Endpoint:** `GET /api/admin/analytics/ticket-tags`

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| start_date | string | ISO 8601 date filter (optional) |
| end_date | string | ISO 8601 date filter (optional) |

**Response:**
```json
{
  "statistics": [
    {"tag": "fertilizer", "tag_id": 1, "count": 12},
    {"tag": "pest", "tag_id": 2, "count": 8},
    {"tag": "pre_planting", "tag_id": 3, "count": 5},
    {"tag": "harvesting", "tag_id": 4, "count": 3},
    {"tag": "irrigation", "tag_id": 5, "count": 7},
    {"tag": "other", "tag_id": 6, "count": 5}
  ],
  "total_tagged": 40,
  "total_resolved": 45,
  "untagged_count": 5,
  "filters": {
    "start_date": "2026-01-01",
    "end_date": "2026-01-22"
  }
}
```

---

### Get Available Tags

**Endpoint:** `GET /api/admin/analytics/ticket-tags/available`

**Response:**
```json
{
  "tags": [
    {
      "id": 1,
      "name": "fertilizer",
      "description": "Questions about fertilizers, soil nutrients, composting..."
    },
    {
      "id": 2,
      "name": "pest",
      "description": "Questions about pests, insects, diseases..."
    },
    ...
  ]
}
```

---

## ✅ Implementation Checklist

### Database
- [x] Add `TicketTag` enum to `backend/models/ticket.py`
- [x] Add `tag` and `tag_confidence` columns to `Ticket` model
- [x] Create Alembic migration
- [x] Run migration: `./dc.sh exec backend alembic upgrade head`

### Tagging Service
- [x] Create `backend/services/tagging_service.py`
- [x] Implement `classify_ticket()` function
- [x] Add tag descriptions for AI context
- [x] Handle OpenAI failures gracefully

### Router Integration
- [x] Update `mark_ticket_resolved` to call tagging service
- [x] Update `_serialize_ticket` to include tag fields
- [x] Import tagging service in tickets router

### Analytics Endpoint
- [x] Create `backend/routers/admin_analytics.py`
- [x] Implement `GET /admin/analytics/ticket-tags`
- [x] Implement `GET /admin/analytics/ticket-tags/available`
- [x] Register router in `main.py`

### Schema Updates
- [x] Add `tag` and `tag_confidence` fields to `TicketModel`

### Testing
- [x] Run linter: `./dc.sh exec backend flake8`
- [x] Run tests: `./dc.sh exec backend pytest tests/test_tickets.py`

---

## 📊 Example Scenarios

### Scenario 1: Pest-Related Conversation

```
Farmer: "My maize plants have small insects eating the leaves"
AI: "This sounds like an aphid infestation. Here's what you can do..."
Farmer: "Should I use pesticides?"
AI: "Yes, you can use neem-based organic pesticides..."

EO closes ticket → AI classifies as PEST (confidence: 0.94)
```

### Scenario 2: Mixed Topics (Dominant = Fertilizer)

```
Farmer: "When should I apply fertilizer?"
AI: "The best time depends on your crop stage..."
Farmer: "Also my plants look yellow"
AI: "Yellow leaves often indicate nitrogen deficiency..."

EO closes ticket → AI classifies as FERTILIZER (confidence: 0.87)
```

### Scenario 3: OpenAI Unavailable

```
EO closes ticket → OpenAI service not configured
Ticket closes successfully with tag=null, tag_confidence=null
No error, graceful degradation
```

---

## 🚨 Important Notes

1. **OpenAI Required** - Auto-tagging only works when OpenAI service is configured
2. **Non-Blocking** - If tagging fails, ticket still closes successfully
3. **Numeric Enum** - Tags stored as integers (1-6) for performance
4. **Access Control** - Analytics respect user administrative areas
5. **Confidence Score** - Ranges from 0.0 to 1.0, useful for quality monitoring
6. **Retroactive Tagging** - Existing closed tickets will have null tags

---

## 🔮 Future Enhancements

### Manual Tag Override
- Allow EOs to manually set/change tags
- Track auto vs manual assignment

### Sub-Categories
- Add more specific tags (e.g., PEST → Aphids, Locusts)
- Hierarchical tag structure

### Tag-Based Routing
- Auto-assign tickets to specialized EOs based on tag
- Priority queues by category

### Confidence Threshold
- Only save tags above certain confidence
- Flag low-confidence tags for review

### Multi-Tag Support
- Allow multiple tags per ticket
- Primary and secondary classifications

---

## 🐛 Troubleshooting

### Tickets Not Getting Tagged

**Problem:** Tickets close successfully but tag is null

**Possible Causes:**
1. OpenAI not configured (`OPENAI_API_KEY` missing)
2. OpenAI disabled in config.json
3. Empty conversation (no messages to classify)

**Debug Steps:**
```bash
# Check backend logs
./dc.sh logs backend -f | grep "TaggingService"

# Look for:
# ✓ "[TaggingService] Classified ticket as PEST (confidence: 0.92)"
# ✗ "[TaggingService] OpenAI not configured, skipping tagging"
```

### Wrong Tag Classification

**Problem:** AI assigns incorrect category

**Solutions:**
1. Review tag descriptions in `tagging_service.py`
2. Check confidence score - low scores indicate uncertainty
3. Consider expanding/refining tag descriptions
4. Report persistent misclassifications for prompt tuning

---

**Status:** Implemented
**Priority:** Medium (Analytics enhancement)
**Dependencies:**
- OpenAI service (already implemented)
- Ticket system (already implemented)
**Blocking:** None
