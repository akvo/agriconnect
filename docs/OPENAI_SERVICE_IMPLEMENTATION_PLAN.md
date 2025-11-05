# Implementation Plan: OpenAI Service Integration

**Date:** 2025-11-04
**Author:** AgriConnect Team
**Status:** Planning
**Objective:** Create a reusable OpenAI service for direct API integration to support features like onboarding workflows, voice transcription, content moderation, and other non-RAG workflows

---

## 📊 Overview

### Purpose

Create a dedicated OpenAI service separate from `external_ai_service.py` (which handles external RAG/chat services with async job callbacks). This new service will provide **direct synchronous OpenAI API integration** for various features.

### Key Differences

| Feature | `external_ai_service.py` | `openai_service.py` (NEW) |
|---------|-------------------------|--------------------------|
| **Purpose** | External RAG/AI services with callbacks | Direct OpenAI API calls |
| **Communication** | Async job-based (create job → callback) | Direct request/response |
| **Configuration** | Database (`service_tokens` table) | Environment variable + config.json |
| **Use Cases** | Chat with KB, document processing | Voice transcription, onboarding, moderation |
| **Response Time** | Async (callback later) | Synchronous or streaming |

---

## 🎯 Design Principles

1. **Separation of Concerns**: Keep external AI service and OpenAI service separate
2. **Configuration-Based**: Use existing `config.json` + `.env` pattern
3. **Reusability**: Provide common methods for various OpenAI features
4. **Error Handling**: Robust retry logic and error handling
5. **Cost Awareness**: Optional token usage logging for monitoring
6. **Type Safety**: Full TypeScript-style typing with Pydantic schemas

---

## 📝 Use Cases

### 1. Voice Message Transcription (Twilio Integration)
```python
# When WhatsApp voice message received
audio_url = twilio_message.media_url
transcription = await openai_service.transcribe_audio(audio_url)
# Use transcription for further processing
```

### 2. Onboarding Workflow
```python
# Generate personalized onboarding messages
response = await openai_service.chat_completion(
    messages=[
        {"role": "system", "content": "You are an agricultural advisor..."},
        {"role": "user", "content": farmer_profile}
    ]
)
```

### 3. Content Moderation
```python
# Check user message before processing
moderation = await openai_service.moderate_content(user_message)
if moderation.flagged:
    # Handle inappropriate content
```

### 4. Structured Data Extraction
```python
# Extract structured data from farmer queries
result = await openai_service.structured_output(
    prompt=farmer_query,
    response_format=FarmerQuerySchema
)
```

### 5. Text Embeddings (Future)
```python
# Create embeddings for semantic search
embedding = await openai_service.create_embedding(text)
```

---

## 📐 Architecture Design

### File Structure

```
backend/
├── config.py                          # UPDATE: Add OpenAI settings
├── config.template.json               # UPDATE: Add openai section
├── config.json                        # Will be auto-updated from template
├── services/
│   ├── openai_service.py             # NEW: Main OpenAI service
│   └── external_ai_service.py        # EXISTING: No changes
├── schemas/
│   └── openai_schemas.py             # NEW: Request/response schemas
├── routers/
│   └── openai_demo.py                # NEW: Demo/example endpoints (optional)
├── tests/
│   └── services/
│       └── test_openai_service.py    # NEW: Unit tests
└── requirements.txt                  # UPDATE: Add openai package
```

### Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  (Routers: whatsapp.py, onboarding.py, etc.)               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Uses
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│              OpenAI Service Layer                            │
│  - chat_completion()                                         │
│  - chat_completion_stream()                                  │
│  - transcribe_audio()                                        │
│  - moderate_content()                                        │
│  - create_embedding()                                        │
│  - structured_output()                                       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Reads config
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│              Configuration Layer                             │
│  - config.json (models, parameters)                         │
│  - .env (OPENAI_API_KEY)                                    │
│  - config.py (Settings class)                               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ API calls
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    OpenAI API                                │
│  - Chat Completions API                                      │
│  - Whisper API (transcription)                              │
│  - Embeddings API                                            │
│  - Moderation API                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Implementation Plan

### Phase 1: Configuration Setup

#### Step 1.1: Update `requirements.txt`

**File:** `backend/requirements.txt`

**Add:**
```txt
openai>=1.30.0
tiktoken>=0.7.0
```

**Notes:**
- `openai`: Official OpenAI Python SDK (latest stable)
- `tiktoken`: Token counting library (for cost estimation)

#### Step 1.2: Update `config.template.json`

**File:** `backend/config.template.json`

**Add new section:**
```json
{
  "message_limit": 10,
  "whatsapp": { ... },
  "escalation": { ... },
  "openai": {
    "enabled": true,
    "default_model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 1000,
    "timeout": 30,
    "max_retries": 3,
    "models": {
      "chat": "gpt-4o-mini",
      "chat_advanced": "gpt-4o",
      "transcription": "whisper-1",
      "embedding": "text-embedding-3-small",
      "moderation": "text-moderation-latest"
    },
    "features": {
      "voice_transcription": {
        "enabled": true,
        "language": "en",
        "response_format": "json",
        "temperature": 0
      },
      "onboarding": {
        "enabled": true,
        "model": "gpt-4o-mini",
        "temperature": 0.8,
        "max_tokens": 500,
        "system_prompt": "You are a helpful agricultural assistant helping farmers get started with AgriConnect. Be friendly, concise, and practical."
      },
      "content_moderation": {
        "enabled": true,
        "auto_flag": true
      },
      "structured_extraction": {
        "enabled": true,
        "model": "gpt-4o-mini",
        "temperature": 0
      }
    },
    "cost_tracking": {
      "enabled": true,
      "log_usage": true
    }
  }
}
```

**Explanation:**
- `enabled`: Master switch for OpenAI features
- `models`: Configurable model names per use case
- `features`: Feature-specific configurations with individual enable flags
- `cost_tracking`: Optional usage logging for monitoring

#### Step 1.3: Update `.env.example`

**File:** `.env.example`

**Add:**
```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
# Optional: Override default organization (if using multiple orgs)
# OPENAI_ORG_ID=org-xxxxxxxxxxxxxxxxxxxxxxxx
```

**Note:** Keep sensitive API key in `.env`, not in `config.json`

#### Step 1.4: Update `config.py`

**File:** `backend/config.py`

**Add to `Settings` class:**
```python
class Settings(BaseSettings):
    # ... existing settings ...

    # OpenAI Configuration
    # API credentials (from .env)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_org_id: Optional[str] = os.getenv("OPENAI_ORG_ID", None)

    # General settings (from config.json)
    openai_enabled: bool = _config.get("openai", {}).get("enabled", False)
    openai_default_model: str = _config.get("openai", {}).get(
        "default_model", "gpt-4o-mini"
    )
    openai_temperature: float = _config.get("openai", {}).get(
        "temperature", 0.7
    )
    openai_max_tokens: int = _config.get("openai", {}).get(
        "max_tokens", 1000
    )
    openai_timeout: int = _config.get("openai", {}).get("timeout", 30)
    openai_max_retries: int = _config.get("openai", {}).get(
        "max_retries", 3
    )

    # Model configurations
    openai_chat_model: str = (
        _config.get("openai", {}).get("models", {}).get("chat", "gpt-4o-mini")
    )
    openai_chat_advanced_model: str = (
        _config.get("openai", {})
        .get("models", {})
        .get("chat_advanced", "gpt-4o")
    )
    openai_transcription_model: str = (
        _config.get("openai", {})
        .get("models", {})
        .get("transcription", "whisper-1")
    )
    openai_embedding_model: str = (
        _config.get("openai", {})
        .get("models", {})
        .get("embedding", "text-embedding-3-small")
    )
    openai_moderation_model: str = (
        _config.get("openai", {})
        .get("models", {})
        .get("moderation", "text-moderation-latest")
    )

    # Feature flags
    openai_voice_transcription_enabled: bool = (
        _config.get("openai", {})
        .get("features", {})
        .get("voice_transcription", {})
        .get("enabled", True)
    )
    openai_voice_transcription_language: str = (
        _config.get("openai", {})
        .get("features", {})
        .get("voice_transcription", {})
        .get("language", "en")
    )
    openai_onboarding_enabled: bool = (
        _config.get("openai", {})
        .get("features", {})
        .get("onboarding", {})
        .get("enabled", True)
    )
    openai_onboarding_system_prompt: str = (
        _config.get("openai", {})
        .get("features", {})
        .get("onboarding", {})
        .get("system_prompt", "")
    )
    openai_content_moderation_enabled: bool = (
        _config.get("openai", {})
        .get("features", {})
        .get("content_moderation", {})
        .get("enabled", True)
    )
    openai_cost_tracking_enabled: bool = (
        _config.get("openai", {})
        .get("cost_tracking", {})
        .get("enabled", False)
    )
```

---

### Phase 2: Core Service Implementation

#### Step 2.1: Create Request/Response Schemas

**File:** `backend/schemas/openai_schemas.py`

```python
"""
OpenAI service schemas for request/response validation.
"""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# Chat Completion Schemas
class ChatMessage(BaseModel):
    """Single chat message"""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Request for chat completion"""
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False


class ChatCompletionResponse(BaseModel):
    """Response from chat completion"""
    content: str
    model: str
    finish_reason: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens


# Audio Transcription Schemas
class TranscriptionRequest(BaseModel):
    """Request for audio transcription"""
    audio_url: Optional[str] = None
    audio_file: Optional[bytes] = None
    language: Optional[str] = "en"
    response_format: Literal["json", "text", "srt", "vtt"] = "json"
    temperature: float = 0


class TranscriptionResponse(BaseModel):
    """Response from audio transcription"""
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None


# Content Moderation Schemas
class ModerationCategory(BaseModel):
    """Individual moderation category"""
    hate: bool = False
    hate_threatening: bool = False
    harassment: bool = False
    harassment_threatening: bool = False
    self_harm: bool = False
    self_harm_intent: bool = False
    self_harm_instructions: bool = False
    sexual: bool = False
    sexual_minors: bool = False
    violence: bool = False
    violence_graphic: bool = False


class ModerationCategoryScores(BaseModel):
    """Confidence scores for moderation categories"""
    hate: float = 0.0
    hate_threatening: float = 0.0
    harassment: float = 0.0
    harassment_threatening: float = 0.0
    self_harm: float = 0.0
    self_harm_intent: float = 0.0
    self_harm_instructions: float = 0.0
    sexual: float = 0.0
    sexual_minors: float = 0.0
    violence: float = 0.0
    violence_graphic: float = 0.0


class ModerationResponse(BaseModel):
    """Response from content moderation"""
    flagged: bool
    categories: ModerationCategory
    category_scores: ModerationCategoryScores


# Embedding Schemas
class EmbeddingRequest(BaseModel):
    """Request for text embedding"""
    text: str
    model: Optional[str] = None


class EmbeddingResponse(BaseModel):
    """Response from embedding"""
    embedding: List[float]
    model: str
    usage: Dict[str, int]


# Structured Output Schemas
class StructuredOutputRequest(BaseModel):
    """Request for structured output (JSON mode)"""
    messages: List[ChatMessage]
    response_format: Dict[str, Any]  # JSON schema
    model: Optional[str] = None
    temperature: float = 0


class StructuredOutputResponse(BaseModel):
    """Response with structured data"""
    data: Dict[str, Any]
    model: str
    usage: Dict[str, int]


# Error Schema
class OpenAIErrorResponse(BaseModel):
    """Error response from OpenAI service"""
    error: str
    error_type: str
    details: Optional[Dict[str, Any]] = None
```

#### Step 2.2: Create OpenAI Service

**File:** `backend/services/openai_service.py`

```python
"""
OpenAI Service for direct API integration.

Provides methods for:
- Chat completion (sync and streaming)
- Audio transcription (Whisper)
- Content moderation
- Text embeddings
- Structured output (JSON mode)

Separate from external_ai_service.py which handles async job-based AI services.
"""
import logging
import httpx
import tiktoken
from typing import Optional, Dict, Any, List, AsyncGenerator
from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletion

from config import settings
from schemas.openai_schemas import (
    ChatMessage,
    ChatCompletionResponse,
    TranscriptionResponse,
    ModerationResponse,
    EmbeddingResponse,
    StructuredOutputResponse,
    OpenAIErrorResponse,
)

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    Service for direct OpenAI API integration.

    Configuration from config.py (loaded from config.json + .env)
    """

    def __init__(self):
        """Initialize OpenAI service with configuration"""
        if not settings.openai_enabled:
            logger.warning(
                "[OpenAIService] OpenAI is disabled in config.json"
            )

        if not settings.openai_api_key:
            logger.warning(
                "[OpenAIService] OPENAI_API_KEY not set in environment"
            )

        # Initialize OpenAI client
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            organization=settings.openai_org_id,
            timeout=settings.openai_timeout,
            max_retries=settings.openai_max_retries,
        )

        # Cost tracking
        self.usage_stats: Dict[str, int] = {
            "total_requests": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

    def is_configured(self) -> bool:
        """Check if service is properly configured"""
        is_valid = bool(
            settings.openai_enabled and
            settings.openai_api_key
        )

        if not is_valid:
            missing = []
            if not settings.openai_enabled:
                missing.append("OpenAI disabled in config.json")
            if not settings.openai_api_key:
                missing.append("OPENAI_API_KEY not set")

            logger.warning(
                f"[OpenAIService] Missing configuration: "
                f"{', '.join(missing)}"
            )

        return is_valid

    def _track_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int
    ) -> None:
        """Track token usage for monitoring"""
        if settings.openai_cost_tracking_enabled:
            self.usage_stats["total_requests"] += 1
            self.usage_stats["prompt_tokens"] += prompt_tokens
            self.usage_stats["completion_tokens"] += completion_tokens
            self.usage_stats["total_tokens"] += (
                prompt_tokens + completion_tokens
            )

            logger.info(
                f"[OpenAIService] Usage: "
                f"+{prompt_tokens} prompt, "
                f"+{completion_tokens} completion "
                f"(total: {self.usage_stats['total_tokens']})"
            )

    def count_tokens(
        self,
        text: str,
        model: Optional[str] = None
    ) -> int:
        """
        Count tokens in text for cost estimation.

        Args:
            text: Text to count tokens
            model: Model name (defaults to configured chat model)

        Returns:
            Number of tokens
        """
        try:
            model = model or settings.openai_chat_model
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(
                f"[OpenAIService] Token counting failed: {e}, "
                f"using estimate"
            )
            # Rough estimate: 1 token ≈ 4 characters
            return len(text) // 4

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[ChatCompletionResponse]:
        """
        Create a chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to config)
            temperature: Sampling temperature (defaults to config)
            max_tokens: Max tokens to generate (defaults to config)
            **kwargs: Additional OpenAI parameters

        Returns:
            ChatCompletionResponse or None if error
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot create chat completion - "
                "not configured"
            )
            return None

        model = model or settings.openai_chat_model
        temperature = (
            temperature
            if temperature is not None
            else settings.openai_temperature
        )
        max_tokens = max_tokens or settings.openai_max_tokens

        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            # Extract response
            choice = response.choices[0]
            content = choice.message.content or ""

            # Track usage
            if response.usage:
                self._track_usage(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )

            logger.info(
                f"✓ Chat completion created with {model} "
                f"({len(content)} chars)"
            )

            return ChatCompletionResponse(
                content=content,
                model=response.model,
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
            )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI API error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Chat completion failed: {e}")
            return None

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Create a streaming chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to config)
            temperature: Sampling temperature (defaults to config)
            max_tokens: Max tokens to generate (defaults to config)
            **kwargs: Additional OpenAI parameters

        Yields:
            Content chunks as they arrive
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot create streaming completion - "
                "not configured"
            )
            return

        model = model or settings.openai_chat_model
        temperature = (
            temperature
            if temperature is not None
            else settings.openai_temperature
        )
        max_tokens = max_tokens or settings.openai_max_tokens

        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )

            logger.info(
                f"✓ Started streaming chat completion with {model}"
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except OpenAIError as e:
            logger.error(f"✗ OpenAI streaming error: {e}")
            return
        except Exception as e:
            logger.error(f"✗ Streaming completion failed: {e}")
            return

    async def transcribe_audio(
        self,
        audio_url: Optional[str] = None,
        audio_file: Optional[bytes] = None,
        language: Optional[str] = None,
        response_format: str = "json",
    ) -> Optional[TranscriptionResponse]:
        """
        Transcribe audio file using Whisper.

        Args:
            audio_url: URL to audio file (downloaded first)
            audio_file: Audio file bytes (direct upload)
            language: Language code (e.g., 'en', 'es')
            response_format: Response format ('json', 'text', 'srt', 'vtt')

        Returns:
            TranscriptionResponse or None if error

        Note: Provide either audio_url OR audio_file, not both
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot transcribe - not configured"
            )
            return None

        if not settings.openai_voice_transcription_enabled:
            logger.warning(
                "[OpenAIService] Voice transcription disabled in config"
            )
            return None

        if not audio_url and not audio_file:
            logger.error(
                "[OpenAIService] Either audio_url or audio_file required"
            )
            return None

        # Download audio if URL provided
        if audio_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(audio_url)
                    response.raise_for_status()
                    audio_file = response.content
            except Exception as e:
                logger.error(f"✗ Failed to download audio: {e}")
                return None

        # Transcribe
        try:
            language = (
                language or
                settings.openai_voice_transcription_language
            )

            # Create temporary file-like object
            from io import BytesIO
            audio_buffer = BytesIO(audio_file)
            audio_buffer.name = "audio.mp3"  # Whisper needs filename

            transcript = await self.client.audio.transcriptions.create(
                model=settings.openai_transcription_model,
                file=audio_buffer,
                language=language,
                response_format=response_format,
            )

            logger.info(
                f"✓ Audio transcribed "
                f"({len(transcript.text) if hasattr(transcript, 'text') else 0} chars)"
            )

            # Handle different response formats
            if response_format == "json":
                return TranscriptionResponse(
                    text=transcript.text,
                    language=getattr(transcript, 'language', language),
                    duration=getattr(transcript, 'duration', None),
                )
            else:
                # For text/srt/vtt, transcript is just a string
                return TranscriptionResponse(
                    text=str(transcript),
                    language=language,
                )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI transcription error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Transcription failed: {e}")
            return None

    async def moderate_content(
        self,
        text: str
    ) -> Optional[ModerationResponse]:
        """
        Check content for policy violations.

        Args:
            text: Text to moderate

        Returns:
            ModerationResponse or None if error
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot moderate - not configured"
            )
            return None

        if not settings.openai_content_moderation_enabled:
            logger.warning(
                "[OpenAIService] Content moderation disabled in config"
            )
            return None

        try:
            response = await self.client.moderations.create(
                input=text,
                model=settings.openai_moderation_model,
            )

            result = response.results[0]

            if result.flagged:
                logger.warning(
                    f"⚠ Content flagged by moderation: "
                    f"{', '.join([k for k, v in result.categories.model_dump().items() if v])}"
                )

            return ModerationResponse(
                flagged=result.flagged,
                categories=result.categories.model_dump(),
                category_scores=result.category_scores.model_dump(),
            )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI moderation error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Moderation failed: {e}")
            return None

    async def create_embedding(
        self,
        text: str,
        model: Optional[str] = None
    ) -> Optional[EmbeddingResponse]:
        """
        Create text embedding vector.

        Args:
            text: Text to embed
            model: Embedding model (defaults to config)

        Returns:
            EmbeddingResponse or None if error
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot create embedding - not configured"
            )
            return None

        model = model or settings.openai_embedding_model

        try:
            response = await self.client.embeddings.create(
                input=text,
                model=model,
            )

            embedding = response.data[0].embedding

            logger.info(
                f"✓ Embedding created with {model} "
                f"(dim: {len(embedding)})"
            )

            return EmbeddingResponse(
                embedding=embedding,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI embedding error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Embedding creation failed: {e}")
            return None

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        response_format: Dict[str, Any],
        model: Optional[str] = None,
    ) -> Optional[StructuredOutputResponse]:
        """
        Get structured output using JSON mode or function calling.

        Args:
            messages: List of message dicts
            response_format: JSON schema for response structure
            model: Model to use (defaults to config)

        Returns:
            StructuredOutputResponse or None if error
        """
        if not self.is_configured():
            logger.error(
                "[OpenAIService] Cannot create structured output - "
                "not configured"
            )
            return None

        model = model or settings.openai_chat_model

        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,  # More deterministic for structured output
            )

            import json
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            # Track usage
            if response.usage:
                self._track_usage(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )

            logger.info(
                f"✓ Structured output created with {model}"
            )

            return StructuredOutputResponse(
                data=data,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
            )

        except OpenAIError as e:
            logger.error(f"✗ OpenAI structured output error: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Structured output failed: {e}")
            return None

    def get_usage_stats(self) -> Dict[str, int]:
        """Get usage statistics"""
        return self.usage_stats.copy()

    def reset_usage_stats(self) -> None:
        """Reset usage statistics"""
        self.usage_stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }
        logger.info("[OpenAIService] Usage stats reset")


# Global service instance
_openai_service: Optional[OpenAIService] = None


def get_openai_service() -> OpenAIService:
    """Get or create OpenAI service singleton"""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service
```

---

### Phase 3: Testing

#### Step 3.1: Create Unit Tests

**File:** `backend/tests/services/test_openai_service.py`

```python
"""
Unit tests for OpenAI service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.openai_service import OpenAIService, get_openai_service
from schemas.openai_schemas import (
    ChatCompletionResponse,
    TranscriptionResponse,
    ModerationResponse,
)


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    with patch('services.openai_service.AsyncOpenAI') as mock:
        yield mock


@pytest.fixture
def openai_service(mock_openai_client):
    """Create OpenAI service with mocked client"""
    with patch('services.openai_service.settings') as mock_settings:
        mock_settings.openai_enabled = True
        mock_settings.openai_api_key = "test_key"
        mock_settings.openai_chat_model = "gpt-4o-mini"
        mock_settings.openai_temperature = 0.7
        mock_settings.openai_max_tokens = 1000
        mock_settings.openai_timeout = 30
        mock_settings.openai_max_retries = 3

        service = OpenAIService()
        return service


@pytest.mark.asyncio
async def test_chat_completion_success(openai_service, mock_openai_client):
    """Test successful chat completion"""
    # Mock response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(content="Test response"),
            finish_reason="stop"
        )
    ]
    mock_response.model = "gpt-4o-mini"
    mock_response.usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30
    )

    openai_service.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Test
    result = await openai_service.chat_completion(
        messages=[{"role": "user", "content": "Hello"}]
    )

    # Assertions
    assert result is not None
    assert isinstance(result, ChatCompletionResponse)
    assert result.content == "Test response"
    assert result.model == "gpt-4o-mini"
    assert result.usage["total_tokens"] == 30


@pytest.mark.asyncio
async def test_chat_completion_not_configured():
    """Test chat completion when not configured"""
    with patch('services.openai_service.settings') as mock_settings:
        mock_settings.openai_enabled = False
        mock_settings.openai_api_key = ""

        service = OpenAIService()
        result = await service.chat_completion(
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert result is None


@pytest.mark.asyncio
async def test_transcribe_audio_success(openai_service):
    """Test successful audio transcription"""
    # Mock response
    mock_response = MagicMock()
    mock_response.text = "Test transcription"
    mock_response.language = "en"

    openai_service.client.audio.transcriptions.create = AsyncMock(
        return_value=mock_response
    )

    with patch('services.openai_service.settings') as mock_settings:
        mock_settings.openai_voice_transcription_enabled = True
        mock_settings.openai_transcription_model = "whisper-1"
        mock_settings.openai_voice_transcription_language = "en"

        # Test with audio bytes
        audio_bytes = b"fake audio data"
        result = await openai_service.transcribe_audio(
            audio_file=audio_bytes
        )

        # Assertions
        assert result is not None
        assert isinstance(result, TranscriptionResponse)
        assert result.text == "Test transcription"


@pytest.mark.asyncio
async def test_moderate_content_success(openai_service):
    """Test successful content moderation"""
    # Mock response
    mock_result = MagicMock()
    mock_result.flagged = True
    mock_result.categories = MagicMock()
    mock_result.categories.model_dump = MagicMock(
        return_value={"hate": True, "violence": False}
    )
    mock_result.category_scores = MagicMock()
    mock_result.category_scores.model_dump = MagicMock(
        return_value={"hate": 0.9, "violence": 0.1}
    )

    mock_response = MagicMock()
    mock_response.results = [mock_result]

    openai_service.client.moderations.create = AsyncMock(
        return_value=mock_response
    )

    with patch('services.openai_service.settings') as mock_settings:
        mock_settings.openai_content_moderation_enabled = True
        mock_settings.openai_moderation_model = "text-moderation-latest"

        # Test
        result = await openai_service.moderate_content("Test content")

        # Assertions
        assert result is not None
        assert isinstance(result, ModerationResponse)
        assert result.flagged is True


def test_count_tokens(openai_service):
    """Test token counting"""
    text = "Hello world, this is a test."
    tokens = openai_service.count_tokens(text)

    # Should return a positive integer
    assert isinstance(tokens, int)
    assert tokens > 0


def test_get_usage_stats(openai_service):
    """Test usage stats retrieval"""
    stats = openai_service.get_usage_stats()

    assert isinstance(stats, dict)
    assert "total_requests" in stats
    assert "total_tokens" in stats


def test_singleton_pattern():
    """Test that get_openai_service returns singleton"""
    service1 = get_openai_service()
    service2 = get_openai_service()

    assert service1 is service2
```

---

### Phase 4: Example Integration

#### Step 4.1: Create Demo Router (Optional)

**File:** `backend/routers/openai_demo.py`

```python
"""
Demo router for OpenAI service integration examples.

This is for testing and demonstration purposes.
Remove or disable in production.
"""
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict
from services.openai_service import get_openai_service
from schemas.openai_schemas import (
    ChatMessage,
    ChatCompletionResponse,
    TranscriptionResponse,
    ModerationResponse,
)

router = APIRouter(prefix="/api/openai-demo", tags=["OpenAI Demo"])


@router.post(
    "/chat",
    response_model=ChatCompletionResponse,
    summary="Test chat completion"
)
async def demo_chat_completion(
    messages: List[Dict[str, str]]
):
    """
    Demo endpoint for chat completion.

    Example request:
    ```json
    {
        "messages": [
            {"role": "user", "content": "What is AgriConnect?"}
        ]
    }
    ```
    """
    service = get_openai_service()

    if not service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI service not configured"
        )

    result = await service.chat_completion(messages=messages)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate response"
        )

    return result


@router.post(
    "/moderate",
    response_model=ModerationResponse,
    summary="Test content moderation"
)
async def demo_moderation(text: str):
    """
    Demo endpoint for content moderation.

    Example: POST /api/openai-demo/moderate?text=Test content
    """
    service = get_openai_service()

    if not service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI service not configured"
        )

    result = await service.moderate_content(text)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to moderate content"
        )

    return result


@router.get(
    "/usage-stats",
    summary="Get OpenAI usage statistics"
)
async def get_usage_stats():
    """Get current usage statistics"""
    service = get_openai_service()
    return service.get_usage_stats()
```

**Register router in `main.py`:**
```python
from routers import openai_demo

app.include_router(openai_demo.router)
```

---

### Phase 5: Documentation

#### Step 5.1: Update CLAUDE.md

**File:** `CLAUDE.md`

**Add section after "External AI Service Integration":**

```markdown
### OpenAI Service Integration

AgriConnect includes a **direct OpenAI API integration** for features that require synchronous responses and don't involve external RAG/knowledge base services.

**Use Cases:**
- Voice message transcription (Whisper)
- Onboarding workflow personalization
- Content moderation
- Structured data extraction
- Text embeddings (future)

**Configuration:**
- API key stored in `.env` file (`OPENAI_API_KEY`)
- Settings managed via `config.json` (models, parameters, feature flags)
- Feature-specific configurations (transcription, onboarding, moderation)

**Service Methods:**
- `chat_completion()` - Generate chat responses
- `chat_completion_stream()` - Streaming chat responses
- `transcribe_audio()` - Transcribe voice messages
- `moderate_content()` - Check content for policy violations
- `create_embedding()` - Generate text embeddings
- `structured_output()` - Get JSON-structured responses

**Example Usage:**
```python
from services.openai_service import get_openai_service

# Transcribe voice message
service = get_openai_service()
transcription = await service.transcribe_audio(
    audio_url="https://example.com/voice.mp3"
)

# Generate onboarding message
response = await service.chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful agricultural assistant..."},
        {"role": "user", "content": "How do I get started?"}
    ]
)
```

**Key Differences from External AI Service:**
- **Synchronous**: Immediate response (not job-based)
- **Direct API**: OpenAI API calls (not external RAG service)
- **Configuration**: Environment variable + config.json (not database)
- **Use Cases**: Transcription, moderation, general AI tasks (not KB-based chat)
```

---

## ✅ Implementation Checklist

### Configuration
- [ ] Add `openai>=1.30.0` and `tiktoken>=0.7.0` to `requirements.txt`
- [ ] Add OpenAI section to `config.template.json`
- [ ] Add `OPENAI_API_KEY` to `.env.example`
- [ ] Update `config.py` with OpenAI settings
- [ ] Copy `config.template.json` to `config.json` (if not exists)
- [ ] Set `OPENAI_API_KEY` in `.env` file

### Core Implementation
- [ ] Create `schemas/openai_schemas.py` with request/response schemas
- [ ] Create `services/openai_service.py` with full implementation
- [ ] Test service initialization and configuration
- [ ] Test each service method individually

### Testing
- [ ] Create `tests/services/test_openai_service.py`
- [ ] Write tests for all service methods
- [ ] Write tests for error handling
- [ ] Write tests for configuration validation
- [ ] Run tests: `./dc.sh exec backend pytest tests/services/test_openai_service.py -v`

### Integration Examples
- [ ] Create `routers/openai_demo.py` (optional demo endpoints)
- [ ] Register demo router in `main.py`
- [ ] Test demo endpoints via Swagger UI
- [ ] Document example integrations

### Documentation
- [ ] Update `CLAUDE.md` with OpenAI service section
- [ ] Add usage examples to documentation
- [ ] Document configuration options
- [ ] Document feature flags

### Future Integrations
- [ ] Integrate with Twilio for voice message transcription
- [ ] Create onboarding workflow using chat completion
- [ ] Add content moderation to user messages
- [ ] Implement structured data extraction for farmer queries

---

## 🎯 Success Criteria

1. **✅ Service configured and initialized** - OpenAI service loads configuration correctly
2. **✅ All methods implemented** - Chat, transcription, moderation, embeddings, structured output
3. **✅ Error handling robust** - Graceful handling of API errors and missing configuration
4. **✅ Tests pass** - All unit tests pass with proper mocking
5. **✅ Configuration flexible** - Easy to enable/disable features and change models
6. **✅ Cost tracking available** - Usage statistics tracked for monitoring
7. **✅ Documentation complete** - Clear usage examples and configuration guide
8. **✅ Type safety** - Full Pydantic schema validation

---

## 🔮 Future Enhancements

### Phase 6: Voice Transcription Integration
- Integrate with Twilio WhatsApp service
- Automatically transcribe voice messages
- Chain transcription with external AI service for response generation

### Phase 7: Onboarding Workflow
- Create personalized onboarding messages
- Guide farmers through initial setup
- Generate contextual help based on user profile

### Phase 8: Content Moderation
- Automatically flag inappropriate content
- Protect farmers from harmful information
- Generate warnings for extension officers

### Phase 9: Embeddings & Semantic Search
- Create embeddings for knowledge base articles
- Implement semantic search
- Find similar farmer queries

### Phase 10: Advanced Features
- Function calling for structured actions
- Vision API for image analysis (crop diseases, etc.)
- Text-to-speech for audio responses
- Fine-tuned models for agricultural domain

---

## 📊 Estimated Effort

- **Phase 1 (Configuration):** 1-2 hours
- **Phase 2 (Core Service):** 4-6 hours
- **Phase 3 (Testing):** 2-3 hours
- **Phase 4 (Examples):** 1-2 hours
- **Phase 5 (Documentation):** 1 hour

**Total:** 9-14 hours (1-2 days)

---

## 🚨 Important Notes

1. **API Key Security**: Never commit `.env` file with real API key
2. **Cost Monitoring**: Enable cost tracking in production to monitor usage
3. **Rate Limits**: OpenAI has rate limits - implement backoff if needed
4. **Feature Flags**: Use config.json to enable/disable features per environment
5. **Testing**: Always test with mocks in unit tests, use test API key for integration tests
6. **Separation**: Keep this service separate from `external_ai_service.py` - different purposes

---

**Status:** Ready for Implementation
**Priority:** Medium (Feature enhancement, not blocking)
**Dependencies:** None (standalone service)
