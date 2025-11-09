# Implementation Plan: WhatsApp Voice Message Transcription

**Date:** 2025-11-09
**Author:** AgriConnect Team
**Status:** Planning
**Objective:** Implement automatic transcription of WhatsApp voice messages using OpenAI Whisper API

---

## 📊 Overview

### Purpose

Enable farmers to send voice messages via WhatsApp, which are automatically transcribed to text and processed through the existing message pipeline. This makes the platform more accessible to farmers who prefer speaking over typing.

### Key Principle

**Voice = Text from the system's perspective**

After transcription, voice messages are treated identically to text messages. No special handling, no separate flows - just convert audio→text at the webhook entry point and continue normally.

### User Experience

```
Farmer: [Sends voice message: "Hello, my maize crop has brown spots"]
    ↓
System: Downloads audio → Transcribes → Body = "Hello, my maize crop has brown spots"
    ↓
System: Processes as normal text message (onboarding/REPLY/WHISPER flow)
    ↓
AI: "Brown spots on maize could indicate fungal infection. Let me help..."
```

### Graceful Failure Handling

If transcription fails or returns empty:
```
Farmer: [Sends corrupted/unclear voice message]
    ↓
System: Transcription fails or returns empty text
    ↓
System: Body = "[Voice message - transcription unavailable]"
    ↓
AI: "I received a voice message but couldn't transcribe it. Please send a text message or try recording again."
```

---

## 🎯 Design Principles

1. **Simplicity** - Voice messages become text, then follow existing flows
2. **No Duplication** - Reuse all existing message processing logic
3. **Temporary Storage** - Use `/tmp` for audio files, delete after transcription
4. **Graceful Degradation** - Failed transcriptions become fallback messages
5. **Future-Proof** - Media type tracking enables future features (images, geolocation)
6. **Audit Trail** - Store original media URL for debugging and compliance

---

## 📐 Architecture Design

### Message Flow

```
┌─────────────────────────────────────────────────────────────┐
│              Twilio WhatsApp Webhook                        │
│    POST /whatsapp/webhook                                   │
│    Form data: From, Body, MessageSid,                       │
│              NumMedia, MediaUrl0, MediaContentType0         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │ Check NumMedia│
         │      > 0?     │
         └───────┬───────┘
                 │
      ┌──────────┴──────────┐
      │                     │
  NO  │                     │ YES + audio/*
      ▼                     ▼
┌─────────────┐    ┌──────────────────────────┐
│ Regular     │    │ Voice Message Handler    │
│ Text Flow   │    │                          │
│             │    │ 1. Download to /tmp      │
│             │    │ 2. Transcribe (OpenAI)   │
│             │    │ 3. Replace Body          │
│             │    │ 4. Save media_url/type   │
│             │    │ 5. Delete /tmp file      │
│             │    └────────┬─────────────────┘
│             │             │
└─────┬───────┘             │
      │                     │
      └──────────┬──────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│         Continue with Existing Message Pipeline             │
│                                                              │
│  ✓ Onboarding check (if no admin data)                     │
│  ✓ REPLY flow (no ticket) or WHISPER flow (has ticket)    │
│  ✓ External AI service processing                          │
│  ✓ All existing business logic                             │
└─────────────────────────────────────────────────────────────┘
```

### Twilio Media URL Authentication

**Important:** Twilio media URLs are **PUBLIC by default** (no auth required):
- Media URLs are publicly accessible without authentication
- Optional: HTTP auth can be enabled in Twilio Console settings
- When auth is enabled, you receive signed URLs (valid for 4 hours)

**Our Implementation:**
- Tries download **without auth first** (default behavior)
- Falls back to Basic Auth if we get 401/403 status codes
- Handles both public and authenticated URLs gracefully
- URLs expire after several hours, so download immediately

### Database Schema

#### Message Model Updates

**File:** `backend/models/message.py`

```python
class MediaType(enum.Enum):
    """Type of media in message"""
    TEXT = "TEXT"              # Regular text message (default)
    VOICE = "VOICE"            # Voice/audio message
    IMAGE = "IMAGE"            # Image (future)
    VIDEO = "VIDEO"            # Video (future)
    DOCUMENT = "DOCUMENT"      # PDF/document (future)
    LOCATION = "LOCATION"      # Geolocation (future)
    OTHER = "OTHER"            # Unknown media type

class Message(Base):
    __tablename__ = "messages"

    # ... existing fields ...

    # Media tracking (for voice, images, etc.)
    media_url = Column(String, nullable=True)
    media_type = Column(
        Enum(MediaType),
        nullable=False,
        server_default=MediaType.TEXT.value
    )
```

**Migration:** `backend/alembic/versions/YYYY_MM_DD_HHMM_add_media_tracking.py`

---

## 🔧 Implementation Plan

### Phase 1: Database Schema

#### Step 1.1: Update Message Model

**File:** `backend/models/message.py`

**Add enum and fields:**

```python
import enum

class MediaType(enum.Enum):
    """Type of media in message"""
    TEXT = "TEXT"
    VOICE = "VOICE"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    LOCATION = "LOCATION"
    OTHER = "OTHER"

class Message(Base):
    __tablename__ = "messages"

    # ... existing fields ...

    # Media tracking
    media_url = Column(String, nullable=True)
    media_type = Column(
        Enum(MediaType),
        nullable=False,
        server_default=MediaType.TEXT.value
    )
```

#### Step 1.2: Create Migration

**File:** `backend/alembic/versions/YYYY_MM_DD_HHMM_add_media_tracking.py`

```python
"""Add media tracking to messages

Revision ID: add_media_tracking
Revises: <previous_revision>
Create Date: 2025-11-09
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_media_tracking'
down_revision = '<previous_revision_id>'
branch_labels = None
depends_on = None

def upgrade():
    # Import the enum from models (follows DeliveryStatus pattern)
    from models.message import MediaType

    # Create enum type
    media_type_enum = sa.Enum(
        MediaType,
        name='mediatype',
        create_type=True
    )
    media_type_enum.create(op.get_bind(), checkfirst=True)

    # Add columns
    op.add_column('messages', sa.Column('media_url', sa.String(), nullable=True))
    op.add_column(
        'messages',
        sa.Column(
            'media_type',
            sa.Enum(MediaType, name='mediatype'),
            nullable=False,
            server_default='TEXT'
        )
    )

def downgrade():
    op.drop_column('messages', 'media_type')
    op.drop_column('messages', 'media_url')
    sa.Enum(name='mediatype').drop(op.get_bind(), checkfirst=True)
```

---

### Phase 2: WhatsApp Service Enhancement

#### Step 2.1: Add Audio Download Method

**File:** `backend/services/whatsapp_service.py`

**Add method:**

```python
import os
import httpx
from typing import Optional

class WhatsAppService:
    # ... existing code ...

    def download_twilio_media(
        self,
        media_url: str,
        save_path: str
    ) -> Optional[str]:
        """
        Download media file from Twilio with authentication.

        Twilio media URLs require Basic Auth using account credentials.

        Args:
            media_url: Twilio media URL (e.g., https://api.twilio.com/2010-04-01/Accounts/.../Media/...)
            save_path: Local path to save file (e.g., /tmp/audio_12345.ogg)

        Returns:
            Path to downloaded file, or None if download failed
        """
        if self.testing_mode:
            logger.info(f"[TESTING MODE] Mocking media download from {media_url}")
            # Create empty file for testing
            with open(save_path, 'wb') as f:
                f.write(b'fake audio data for testing')
            return save_path

        try:
            # Download with Basic Auth
            auth = (self.account_sid, self.auth_token)

            response = httpx.get(media_url, auth=auth, timeout=30.0)
            response.raise_for_status()

            # Save to file
            with open(save_path, 'wb') as f:
                f.write(response.content)

            logger.info(
                f"✓ Downloaded media from Twilio: {len(response.content)} bytes → {save_path}"
            )
            return save_path

        except httpx.HTTPError as e:
            logger.error(f"✗ Failed to download Twilio media: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Unexpected error downloading media: {e}")
            return None
```

---

### Phase 3: Webhook Integration

#### Step 3.1: Update WhatsApp Webhook

**File:** `backend/routers/whatsapp.py`

**Add imports:**

```python
import os
import uuid
from services.openai_service import get_openai_service
from models.message import MediaType
```

**Add form parameters:**

```python
@router.post("/webhook")
async def whatsapp_webhook(
    From: Annotated[str, Form()],
    MessageSid: Annotated[str, Form()],
    Body: Annotated[str, Form()] = "",  # OPTIONAL: Empty for voice messages
    ButtonPayload: Annotated[Optional[str], Form()] = None,
    NumMedia: Annotated[Optional[int], Form()] = 0,  # NEW: Number of media files
    MediaUrl0: Annotated[Optional[str], Form()] = None,  # NEW: First media URL
    MediaContentType0: Annotated[Optional[str], Form()] = None,  # NEW: Media type
    db: Session = Depends(get_db),
):
```

**IMPORTANT:** The `Body` parameter must be **optional with default empty string**. When Twilio sends a voice message, the `Body` field is often empty or missing. Making it required causes 422 Unprocessable Entity errors.

**Add voice message handling (BEFORE existing code):**

```python
async def whatsapp_webhook(...):
    """
    Handle incoming WhatsApp messages and button responses.

    Flow 1: Voice message → Transcribe → Process as text
    Flow 2: Regular message → Process normally
    Flow 3: Button "escalate" → Create ticket + WHISPER
    """
    try:
        phone_number = From.replace("whatsapp:", "")
        media_url = None
        media_type = MediaType.TEXT

        # ========================================
        # VOICE MESSAGE TRANSCRIPTION
        # ========================================
        if NumMedia and NumMedia > 0 and MediaContentType0 and "audio" in MediaContentType0:
            logger.info(
                f"Voice message received from {phone_number}: "
                f"{MediaContentType0} at {MediaUrl0}"
            )

            media_url = MediaUrl0
            media_type = MediaType.VOICE

            # Generate unique temp file path
            temp_file = f"/tmp/voice_{uuid.uuid4().hex}.ogg"

            try:
                # Download audio to /tmp
                whatsapp_service = WhatsAppService()
                downloaded_path = whatsapp_service.download_twilio_media(
                    media_url=MediaUrl0,
                    save_path=temp_file
                )

                if downloaded_path:
                    # Transcribe with OpenAI
                    openai_service = get_openai_service()

                    # Read audio file as bytes
                    with open(downloaded_path, 'rb') as f:
                        audio_bytes = f.read()

                    transcription = await openai_service.transcribe_audio(
                        audio_file=audio_bytes
                    )

                    # Check if transcription succeeded
                    if transcription and transcription.text.strip():
                        Body = transcription.text.strip()
                        logger.info(
                            f"✓ Transcribed voice message from {phone_number}: "
                            f"{Body[:50]}..."
                        )
                    else:
                        # Transcription failed or empty
                        Body = "[Voice message - transcription unavailable]"
                        logger.warning(
                            f"⚠ Voice transcription failed or empty for {phone_number}"
                        )
                else:
                    # Download failed
                    Body = "[Voice message - download failed]"
                    logger.error(f"✗ Failed to download voice message from {phone_number}")

            except Exception as e:
                # Any error in transcription flow
                Body = "[Voice message - transcription error]"
                logger.error(f"✗ Error transcribing voice message: {e}")

            finally:
                # ALWAYS delete temp file
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        logger.debug(f"Deleted temp file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file {temp_file}: {e}")

        # ========================================
        # CONTINUE WITH EXISTING MESSAGE FLOW
        # (Body is now either original text or transcribed text)
        # ========================================

        # Check if message already processed
        existing_message = (
            db.query(Message).filter(Message.message_sid == MessageSid).first()
        )
        if existing_message:
            return {"status": "success", "message": "Already processed"}

        # ... rest of existing code (customer creation, onboarding, etc.) ...
```

**Update message creation to include media fields:**

```python
# When creating messages, add media fields:

# For regular messages:
message = Message(
    message_sid=MessageSid,
    customer_id=customer.id,
    body=Body,  # Either original text or transcribed text
    from_source=MessageFrom.CUSTOMER,
    status=MessageStatus.PENDING,
    media_url=media_url,  # NEW: Twilio media URL or None
    media_type=media_type,  # NEW: VOICE or TEXT
)
```

---

### Phase 4: Configuration

No new configuration needed! Uses existing OpenAI service settings:

```json
{
  "openai": {
    "features": {
      "voice_transcription": {
        "enabled": true,
        "language": "en",
        "response_format": "json",
        "temperature": 0
      }
    }
  }
}
```

---

### Phase 5: Testing

#### Step 5.1: Unit Tests

**File:** `backend/tests/services/test_whatsapp_voice.py`

```python
"""
Unit tests for voice message handling in WhatsApp service.
"""
import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from services.whatsapp_service import WhatsAppService
from services.openai_service import get_openai_service
from models.message import MediaType

@pytest.fixture
def mock_twilio_media_url():
    return "https://api.twilio.com/2010-04-01/Accounts/ACXXX/Media/MEXXX"

def test_download_twilio_media_success(tmp_path):
    """Test successful media download"""
    service = WhatsAppService()
    save_path = tmp_path / "test_audio.ogg"

    with patch('httpx.get') as mock_get:
        # Mock successful download
        mock_response = Mock()
        mock_response.content = b"fake audio data"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = service.download_twilio_media(
            media_url="https://api.twilio.com/test.ogg",
            save_path=str(save_path)
        )

        # Verify
        assert result == str(save_path)
        assert save_path.exists()
        assert save_path.read_bytes() == b"fake audio data"

        # Verify auth was used
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert 'auth' in call_kwargs

def test_download_twilio_media_failure():
    """Test failed media download"""
    service = WhatsAppService()

    with patch('httpx.get') as mock_get:
        # Mock HTTP error
        mock_get.side_effect = Exception("Network error")

        result = service.download_twilio_media(
            media_url="https://api.twilio.com/test.ogg",
            save_path="/tmp/test.ogg"
        )

        # Should return None on failure
        assert result is None

@pytest.mark.asyncio
async def test_voice_message_transcription_success(mock_twilio_media_url):
    """Test successful voice message transcription"""
    # Mock OpenAI transcription
    with patch('services.openai_service.AsyncOpenAI') as mock_openai:
        mock_transcript = Mock()
        mock_transcript.text = "Hello, I need help with my crops"

        mock_openai.return_value.audio.transcriptions.create = AsyncMock(
            return_value=mock_transcript
        )

        openai_service = get_openai_service()

        # Transcribe
        result = await openai_service.transcribe_audio(
            audio_file=b"fake audio data"
        )

        # Verify
        assert result is not None
        assert result.text == "Hello, I need help with my crops"

@pytest.mark.asyncio
async def test_voice_message_webhook_integration(client, db):
    """Test voice message through webhook"""
    # Mock download and transcription
    with patch('services.whatsapp_service.WhatsAppService.download_twilio_media') as mock_download, \
         patch('services.openai_service.get_openai_service') as mock_openai_svc:

        # Mock download
        mock_download.return_value = "/tmp/test_audio.ogg"

        # Mock transcription
        mock_transcript = Mock()
        mock_transcript.text = "My maize has brown spots"
        mock_openai = Mock()
        mock_openai.transcribe_audio = AsyncMock(return_value=mock_transcript)
        mock_openai_svc.return_value = mock_openai

        # Create temp file for cleanup test
        with open("/tmp/test_audio.ogg", "wb") as f:
            f.write(b"fake audio")

        # Send voice message webhook
        response = await client.post(
            "/whatsapp/webhook",
            data={
                "From": "whatsapp:+255123456789",
                "Body": "",
                "MessageSid": "SMXXX123",
                "NumMedia": 1,
                "MediaUrl0": "https://api.twilio.com/media/MEXXX",
                "MediaContentType0": "audio/ogg"
            }
        )

        assert response.status_code == 200

        # Verify message created with transcription
        message = db.query(Message).filter_by(message_sid="SMXXX123").first()
        assert message is not None
        assert message.body == "My maize has brown spots"
        assert message.media_type == MediaType.VOICE
        assert message.media_url == "https://api.twilio.com/media/MEXXX"

        # Verify temp file was cleaned up
        assert not os.path.exists("/tmp/test_audio.ogg")
```

#### Step 5.2: Integration Test Scenarios

1. **Successful transcription** - Voice → text → normal flow
2. **Failed transcription** - Voice → fallback message → AI responds
3. **Download failure** - Voice → fallback message → AI responds
4. **Cleanup verification** - Temp files always deleted
5. **Media tracking** - media_url and media_type saved correctly
6. **Onboarding with voice** - Voice message triggers onboarding flow
7. **REPLY/WHISPER with voice** - Voice messages work in all flows

---

## ✅ Implementation Checklist

### Phase 1: Database
- [ ] Add `MediaType` enum to `backend/models/message.py`
- [ ] Add `media_url` and `media_type` columns to `Message` model
- [ ] Create Alembic migration `add_media_tracking.py`
- [ ] Run migration: `./dc.sh exec backend alembic upgrade head`
- [ ] Verify columns exist: `./dc.sh exec backend bash -c "cd /app && python3 -c \"from database import SessionLocal; from models.message import Message; import sqlalchemy; db = SessionLocal(); print(sqlalchemy.inspect(Message).columns.keys()); db.close()\""`

### Phase 2: WhatsApp Service
- [ ] Add `download_twilio_media()` method to `WhatsAppService`
- [ ] Add httpx import for HTTP downloads
- [ ] Implement Basic Auth with Twilio credentials
- [ ] Add testing mode support for mocks
- [ ] Test download with real Twilio media URL

### Phase 3: Webhook Integration
- [ ] Add `NumMedia`, `MediaUrl0`, `MediaContentType0` form parameters
- [ ] Add voice message detection logic (`NumMedia > 0` and `audio`)
- [ ] Add download → transcribe → replace Body flow
- [ ] Add fallback handling for failed transcriptions
- [ ] Add temp file cleanup (`os.remove` in finally block)
- [ ] Update message creation to include `media_url` and `media_type`
- [ ] Test with mock Twilio webhook data

### Phase 4: Testing
- [ ] Write `test_download_twilio_media_success()`
- [ ] Write `test_download_twilio_media_failure()`
- [ ] Write `test_voice_message_transcription_success()`
- [ ] Write `test_voice_message_webhook_integration()`
- [ ] Write `test_voice_transcription_fallback()`
- [ ] Write `test_temp_file_cleanup()`
- [ ] Run all tests: `./dc.sh exec backend pytest tests/ -v -k voice`

### Phase 5: End-to-End Testing
- [ ] Configure Twilio webhook to point to dev environment
- [ ] Send real voice message via WhatsApp
- [ ] Verify transcription appears in message body
- [ ] Verify media_url and media_type saved correctly
- [ ] Verify temp files cleaned up in `/tmp`
- [ ] Verify message flows normally through onboarding/REPLY/WHISPER
- [ ] Test with unclear audio (verify fallback message)
- [ ] Test with long voice message (>1min)

### Phase 6: Documentation
- [ ] Update `CLAUDE.md` with voice message section
- [ ] Document Twilio webhook parameters
- [ ] Document media type enum values
- [ ] Add troubleshooting guide

---

## 🎯 Success Criteria

1. **✅ Voice messages transcribed** - Audio converted to text automatically
2. **✅ No special flows** - Voice = text after transcription
3. **✅ Graceful failures** - Failed transcriptions become fallback messages
4. **✅ Temp files cleaned** - No audio files left in `/tmp`
5. **✅ Media tracked** - `media_url` and `media_type` saved for audit
6. **✅ Works with onboarding** - Voice triggers location collection if needed
7. **✅ Works with REPLY/WHISPER** - Voice works in all existing flows
8. **✅ AI handles fallbacks** - AI responds naturally to transcription failures
9. **✅ Future-proof** - `MediaType` enum supports images, video, location
10. **✅ All tests pass** - Unit and integration tests green

---

## 📊 Example Scenarios

### Scenario 1: Successful Voice Transcription

```
Farmer sends voice message: "Habari, mahindi yangu yana mawaa ya kahawia"

Twilio webhook data:
{
  "From": "whatsapp:+255712345678",
  "Body": "",
  "MessageSid": "SM123abc",
  "NumMedia": 1,
  "MediaUrl0": "https://api.twilio.com/2010-04-01/Accounts/ACXXX/Media/MEXXX",
  "MediaContentType0": "audio/ogg; codecs=opus"
}

System flow:
1. Detect NumMedia=1 and audio type
2. Download to /tmp/voice_abc123.ogg
3. Transcribe: "Habari, mahindi yangu yana mawaa ya kahawia"
4. Delete /tmp/voice_abc123.ogg
5. Save message:
   - body: "Habari, mahindi yangu yana mawaa ya kahawia"
   - media_url: "https://api.twilio.com/2010-04-01/Accounts/ACXXX/Media/MEXXX"
   - media_type: VOICE
6. Continue with normal flow (onboarding/REPLY/WHISPER)

AI response:
"Mawaa ya kahawia kwenye mahindi yanaweza kuonyesha maambukizi ya fungi..."
```

### Scenario 2: Transcription Failure (Graceful Degradation)

```
Farmer sends very unclear/corrupted voice message

System flow:
1. Download succeeds
2. Transcription returns empty string
3. Body = "[Voice message - transcription unavailable]"
4. Save message with VOICE type
5. Continue with normal flow

AI response:
"I received a voice message but couldn't transcribe it clearly.
Could you please send a text message or try recording again?"
```

### Scenario 3: Voice + Onboarding

```
New farmer (no admin data) sends voice: "Niko Kivulini, Mwanga, Kilimanjaro"

System flow:
1. Transcribe: "Niko Kivulini, Mwanga, Kilimanjaro"
2. Check onboarding → needs location data
3. Onboarding service extracts location from transcription
4. Matches ward hierarchically
5. Saves location
6. Continues with AI response

Onboarding response:
"Asante! Umesajiliwa katika Kivulini ward, Mwanga district, Kilimanjaro.
Je, unaweza kunisaidia vipi leo?"
```

---

## 🚨 Important Notes

1. **Twilio Media URLs are PUBLIC by default** - No auth required unless HTTP auth enabled in Twilio Console
2. **Body Parameter Must Be Optional** - Voice messages send empty Body, making it required causes 422 errors
3. **Media URLs are Temporary** - Expire after ~4 hours (signed URLs), download immediately
4. **Temp File Cleanup** - ALWAYS use try/finally to ensure cleanup
5. **OpenAI API Key Required** - Voice transcription uses existing OpenAI service
6. **Media Type is Future-Proof** - Enum supports images, video, geolocation
7. **Testing Mode** - WhatsApp service already has mock support
8. **No Breaking Changes** - Existing text messages work identically
9. **Fallback Messages** - Let AI handle transcription failures naturally
10. **Container /tmp** - Files stored in backend container's /tmp, not host
11. **Language Detection** - OpenAI Whisper auto-detects language (or use config)

---

## 🐛 Troubleshooting

### 422 Unprocessable Entity Error

**Problem:** Webhook returns 422 error when receiving voice messages

**Cause:** The `Body` form parameter is marked as required, but Twilio sends voice messages without a Body field (or with empty Body).

**Solution:**
```python
# ❌ WRONG - Required parameter causes 422 for voice messages
Body: Annotated[str, Form()],

# ✅ CORRECT - Optional with default empty string
Body: Annotated[str, Form()] = "",
```

**Verification:**
```bash
# Check backend logs for 422 errors
./dc.sh logs backend --tail=50 | grep "422"

# After fix, voice messages should return 200
# No more 422 errors from Twilio webhook IPs
```

### Voice Message Not Transcribed

**Problem:** Voice message saved but Body is fallback message

**Possible Causes:**
1. OpenAI API key not set or invalid
2. Audio download failed (check media URL)
3. Audio format not supported by Whisper
4. Network timeout during transcription

**Debug Steps:**
```bash
# Check backend logs
./dc.sh logs backend -f | grep "voice"

# Look for:
# ✓ "Voice message received from..."
# ✓ "Downloaded media from Twilio..."
# ✓ "Transcribed voice message from..."
# ✗ "Failed to download voice message..."
# ✗ "Voice transcription failed or empty..."
```

### Temp Files Not Cleaned Up

**Problem:** `/tmp` directory filling up with audio files

**Solution:** Ensure `finally` block always executes:
```python
try:
    # Download and transcribe
    pass
finally:
    # ALWAYS delete temp file
    if os.path.exists(temp_file):
        os.remove(temp_file)
```

### Media URL Download Fails

**Problem:** Download returns None or 401/403 errors

**Solutions:**
1. Check if Twilio HTTP auth is enabled (should be disabled by default)
2. Verify account SID and auth token are correct
3. Try downloading media URL within 4 hours (signed URLs expire)
4. Check if URL is accessible from backend container

---

## 🔮 Future Enhancements

### Phase 7: Image Messages
- Detect `image/*` in `MediaContentType0`
- Download image to /tmp
- Use OpenAI Vision API to analyze image
- Extract text description or detect crop diseases
- Reuse `media_url` and `MediaType.IMAGE`

### Phase 8: Location Messages
- Detect `MediaContentType0 = "location"`
- Extract latitude/longitude from webhook
- Reverse geocode to administrative area
- Auto-complete onboarding with location
- Reuse `MediaType.LOCATION`

### Phase 9: Video Messages
- Detect `video/*` in `MediaContentType0`
- Extract audio track and transcribe
- Or extract keyframes for analysis
- Reuse `MediaType.VIDEO`

### Phase 10: Document Messages
- Detect `application/pdf` or `document`
- Extract text from PDFs
- Process agricultural documents
- Reuse `MediaType.DOCUMENT`

---

## 📊 Estimated Effort

- **Phase 1 (Database):** 1 hour
- **Phase 2 (WhatsApp Service):** 2 hours
- **Phase 3 (Webhook):** 3 hours
- **Phase 4 (Testing):** 3 hours
- **Phase 5 (E2E Testing):** 2 hours
- **Phase 6 (Documentation):** 1 hour

**Total:** 12 hours (1.5 days)

---

**Status:** Ready for Implementation
**Priority:** Medium (Accessibility enhancement)
**Dependencies:**
- OpenAI service with Whisper transcription (already implemented)
- Twilio WhatsApp integration (already implemented)
**Blocking:** None
