"""
OpenAI service schemas for request/response validation.
"""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# Chat Completion Schemas
class ChatMessage(BaseModel):
    """Single chat message"""

    role: Literal["system", "user", "assistant", "developer"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Request for chat completion"""

    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False


class ChatCompletionUsage(BaseModel):
    """Token usage information"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Response from chat completion"""

    content: str
    model: str
    finish_reason: str
    usage: ChatCompletionUsage


# Audio Transcription Schemas
class TranscriptionRequest(BaseModel):
    """Request for audio transcription"""

    audio_url: Optional[str] = None
    audio_file: Optional[bytes] = None
    language: Optional[str] = "en"
    response_format: Literal["json", "text", "srt", "vtt", "verbose_json"] = (
        "json"
    )
    temperature: float = 0


class TranscriptionResponse(BaseModel):
    """Response from audio transcription"""

    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    words: Optional[List[Dict[str, Any]]] = None
    segments: Optional[List[Dict[str, Any]]] = None


# Content Moderation Schemas
class ModerationCategory(BaseModel):
    """Individual moderation category flags"""

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
    usage: ChatCompletionUsage


# Error Schema
class OpenAIErrorResponse(BaseModel):
    """Error response from OpenAI service"""

    error: str
    error_type: str
    details: Optional[Dict[str, Any]] = None
