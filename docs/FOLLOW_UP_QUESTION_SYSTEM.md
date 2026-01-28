# Follow-Up Question System

## Overview

The Follow-Up Question System enhances the quality of AI responses by gathering additional context from farmers before engaging the external AI service. When a farmer sends a question in REPLY mode (no existing ticket, onboarding completed), the system asks ONE contextual follow-up question using internal OpenAI before forwarding the conversation to the external AI/RAG service.

## Purpose

- **Gather more context**: Understand the farmer's specific situation before generating a response
- **Improve AI response quality**: More context leads to more relevant and helpful answers
- **Ask clarifying questions**: Inquire about the specific problem, crop affected, duration of issue, or steps already taken

## System Architecture

### Components

1. **MessageType.FOLLOW_UP (4)**: New enum value to track follow-up questions in message history
2. **Configuration**: Enable/disable via `config.json` under `openai.features.follow_up`
3. **FollowUpService**: Service class in `/backend/services/follow_up_service.py`
4. **WhatsApp Router Integration**: Intercepts REPLY mode before external AI

### Message Flow

```
Customer sends message
       |
       v
  In REPLY mode?  --No--> (WHISPER mode or onboarding)
       |
      Yes
       v
  Follow-up enabled?  --No--> Send to External AI
       |
      Yes
       v
  Should ask follow-up?  --No--> Send to External AI
       |                         (already asked in this convo)
      Yes
       v
  Generate follow-up (OpenAI)
       |
       v
  Send to customer (WhatsApp)
       |
       v
  Store with MessageType.FOLLOW_UP
       |
       v
  Return success (await customer response)
       |
       v
  [Customer responds]
       |
       v
  FOLLOW_UP in history --> Send to External AI
```

## Detection Logic

The system determines when to ask a follow-up question based on chat history and ticket status.

### Algorithm

```python
def should_ask_follow_up(customer, chat_history) -> bool:
    """
    Returns True if:
    - No FOLLOW_UP in chat history, OR
    - There's a closed ticket that was resolved AFTER the last FOLLOW_UP
      (indicating a new conversation after ticket closure)
    """
    # Find last FOLLOW_UP in chat history
    last_follow_up = find_last_follow_up(chat_history)

    # No follow-up in history → ask one
    if last_follow_up is None:
        return True

    # Check if there's a ticket closed AFTER the last follow-up
    last_resolved_ticket = get_last_resolved_ticket(customer)

    if last_resolved_ticket is None:
        # No resolved ticket, but follow-up exists → don't ask again
        return False

    # If ticket was resolved AFTER the last follow-up was sent,
    # this is a new conversation → ask follow-up again
    if last_resolved_ticket.resolved_at > last_follow_up.created_at:
        return True

    # Follow-up was sent after ticket closure → don't ask again
    return False
```

### Scenarios

| Scenario | Has FOLLOW_UP | Has Resolved Ticket | Result |
|----------|--------------|---------------------|--------|
| First message ever | No | No | Ask follow-up |
| Already asked | Yes | No | Don't ask |
| Asked, ticket closed | Yes | Yes (after FOLLOW_UP) | Ask follow-up |
| New convo after closure, already asked | Yes | Yes (before FOLLOW_UP) | Don't ask |

## Configuration

### config.json

```json
{
  "openai": {
    "features": {
      "follow_up": {
        "enabled": true,
        "temperature": 0.7,
        "max_tokens": 150
      }
    }
  }
}
```

### Settings (config.py)

- `follow_up_enabled`: Enable/disable the feature (default: `true`)
- `follow_up_temperature`: OpenAI temperature for generation (default: `0.7`)
- `follow_up_max_tokens`: Maximum tokens for follow-up question (default: `150`)

## System Prompts

### English

```
You are a helpful agricultural assistant. A farmer has just asked a question.
Your task is to ask ONE brief, friendly follow-up question to better understand their situation.

Consider asking about:
- What specific crop or livestock is affected?
- How long has this problem been occurring?
- What have they already tried?
- What symptoms are they seeing?

Keep your question short (1-2 sentences) and conversational.
Do NOT answer their question yet - just ask for clarification.

Farmer's question: {original_question}

Farmer context:
- Name: {name}
- Crop: {crop_type}
- Location: {location}
```

### Swahili

```
Wewe ni msaidizi wa kilimo. Mkulima ametuma swali.
Kazi yako ni kuuliza swali MOJA fupi na la kirafiki ili kuelewa hali yake vizuri.

Fikiria kuuliza kuhusu:
- Ni zao gani au mifugo gani imeathirika?
- Tatizo hili limekuwapo kwa muda gani?
- Wamejaribu nini tayari?
- Wanaona dalili gani?

Weka swali lako fupi (sentensi 1-2) na la mazungumzo.
USIJIBU swali lao bado - uliza tu kwa ufafanuzi.

Swali la mkulima: {original_question}

Muktadha wa mkulima:
- Jina: {name}
- Zao: {crop_type}
- Mahali: {location}
```

## Service Implementation

### FarmerContext

```python
@dataclass
class FarmerContext:
    name: Optional[str] = None
    language: str = "en"
    crop_type: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None
```

### FollowUpService Methods

| Method | Description |
|--------|-------------|
| `should_ask_follow_up(customer, chat_history)` | Determine if follow-up is needed |
| `generate_follow_up_question(customer, original_question)` | Generate question via OpenAI |
| `ask_follow_up(customer, message, phone_number)` | Generate, send, and store follow-up |

## Database Schema

No new tables required. Uses existing `messages` table with new `MessageType.FOLLOW_UP` value.

```sql
-- MessageType enum values:
-- REPLY = 1
-- WHISPER = 2
-- BROADCAST = 3
-- FOLLOW_UP = 4  (NEW)
```

## Testing

### Unit Tests

```bash
./dc.sh exec backend pytest tests/test_follow_up_service.py -v
```

### Test Scenarios

1. **Should ask follow-up when no FOLLOW_UP in history**
2. **Should NOT ask when FOLLOW_UP already exists (no ticket)**
3. **Should ask when FOLLOW_UP exists BUT ticket was resolved AFTER it**
4. **Should NOT ask when FOLLOW_UP was sent AFTER ticket was resolved**
5. **Generates English follow-up for EN customer**
6. **Generates Swahili follow-up for SW customer**
7. **Sends via WhatsApp and stores with MessageType.FOLLOW_UP**

### Integration Testing

1. Send test WhatsApp message → verify follow-up is received
2. Reply to follow-up → verify it goes to external AI
3. Test new conversation after ticket closure:
   - Send message → receive follow-up
   - Reply → goes to external AI
   - Escalate to support → ticket created
   - Support closes ticket
   - Send new message → should receive NEW follow-up

### Disable Test

Set `enabled: false` in config.json, verify normal flow (no follow-up)

## Limitations

- Only applies to REPLY mode (no existing ticket, onboarding completed)
- One follow-up per conversation (until ticket closure)
- Depends on OpenAI service availability
- Follow-up generation may add latency to first response

## Related Files

- `/backend/schemas/callback.py` - MessageType enum
- `/backend/config.json` - Configuration settings
- `/backend/config.py` - Settings class
- `/backend/services/follow_up_service.py` - Service implementation
- `/backend/routers/whatsapp.py` - Router integration
- `/backend/tests/test_follow_up_service.py` - Tests
