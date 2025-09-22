from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class CallbackStage(str, Enum):
    QUEUED = "queued"
    DONE = "done"
    FAILED = "failed"
    TIMEOUT = "timeout"


class JobType(str, Enum):
    CHAT = "chat"
    UPLOAD = "upload"


class MessageType(int, Enum):
    REPLY = 1  # Send directly to customer via WhatsApp
    WHISPER = 2  # Store as suggestion for EO review


class Citation(BaseModel):
    title: str = Field(..., description="Title of the cited source")
    url: str = Field(..., description="URL of the cited source")


class CallbackResult(BaseModel):
    answer: str = Field(
        ...,
        description="AI-generated response to the user query",
        example="Plant maize during rainy season for optimal yield.",
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Sources used to generate the AI response",
        example=[
            {
                "title": "Maize Growing Guide",
                "url": "https://example.com/maize-guide",
            }
        ],
    )


class AICallbackParams(BaseModel):
    """Parameters specific to AI processing callbacks"""

    message_id: Optional[int] = Field(
        None,
        description="ID of the original message that triggered AI processing",
        example=123,
    )
    message_type: Optional[MessageType] = Field(
        None,
        description="REPLY (1) sends to customer, WHISPER (2) EO suggestion",
        example=1,
    )


class KBCallbackParams(BaseModel):
    """Parameters specific to Knowledge Base processing callbacks"""

    kb_id: Optional[int] = Field(
        None, description="Knowledge base ID that was processed", example=456
    )
    user_id: Optional[int] = Field(
        None,
        description="ID of the user who initiated the KB processing",
        example=789,
    )


class AIWebhookCallback(BaseModel):
    """Webhook callback payload for AI processing"""

    job_id: str = Field(..., description="Unique AI processing job identifier")
    stage: CallbackStage = Field(..., description="Processing stage")
    result: Optional[CallbackResult] = Field(
        None, description="AI results (when stage='done')"
    )
    callback_params: Optional[AICallbackParams] = Field(
        None, description="AI-specific parameters"
    )
    trace_id: Optional[str] = Field(
        None, description="Tracing ID for debugging"
    )
    job: JobType = Field(..., description="Job type")


class KBWebhookCallback(BaseModel):
    """Webhook callback payload for Knowledge Base processing"""

    job_id: str = Field(..., description="Unique KB processing job identifier")
    stage: CallbackStage = Field(..., description="Processing stage")
    callback_params: Optional[KBCallbackParams] = Field(
        None, description="KB-specific parameters"
    )
    trace_id: Optional[str] = Field(
        None, description="Tracing ID for debugging"
    )
    job: JobType = Field(..., description="Job type")
